// LeiYure Community


#include "LLM/NPCBrainComponent.h"
//#include "Json.h"
//#include "JsonUtilities.h"
#include "Serialization/JsonSerializer.h"
#include "Dom/JsonObject.h"


// Sets default values for this component's properties
UNPCBrainComponent::UNPCBrainComponent()
{
	// 事件驱动，不用每帧tick
	PrimaryComponentTick.bCanEverTick = false;
	LastParsedStringLength = 0;
}


// Called when the game starts
void UNPCBrainComponent::BeginPlay()
{
	Super::BeginPlay();

	// ...
	
}

// 流式输出的截取和分流
void UNPCBrainComponent::OnStreamProgress(FHttpRequestPtr Request, uint64 BytesSent, uint64 BytesReceived)
{
    if (!Request.IsValid() || Request->GetStatus() != EHttpRequestStatus::Processing) return;

    // 拿到截至目前的所有下载内容
    FString FullResponse = Request->GetResponse()->GetContentAsString();
    int32 CurrentLength = FullResponse.Len();

    // 如果有新数据到来
    if (CurrentLength > LastParsedStringLength)
    {
        // 1. 增量截取：只保留这次新收到的字符串片段
        FString NewChunk = FullResponse.RightChop(LastParsedStringLength);
        LastParsedStringLength = CurrentLength;

        TArray<FString> Lines;
        // 2. 按行切分，剔除空行（SSE 协议以 \n\n 结尾）
        NewChunk.ParseIntoArrayLines(Lines, true);

        for (const FString& Line : Lines)
        {
            // SSE 数据规范：只有 data: 开头的才是有效载荷
            if (Line.StartsWith(TEXT("data:")))
            {
                // 去掉 "data: " 前缀，拿到纯正的内容
                FString Payload = Line.RightChop(5).TrimStartAndEnd();
                if (Payload.IsEmpty() || Payload == TEXT("[DONE]")) continue;

                // ---------------------------------------------------------
                // 判断这段内容是动作指令，还是台词文本
                // ---------------------------------------------------------

                // 分支 A：隐蔽数据帧（判断是否为 JSON 且包含 meta 关键字）
                if (Payload.StartsWith(TEXT("{")) && Payload.Contains(TEXT("\"meta\"")))
                {
                    TSharedPtr<FJsonObject> JsonObj;
                    TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Payload);

                    // 尝试将首帧解析为 JSON
                    if (FJsonSerializer::Deserialize(Reader, JsonObj))
                    {
                        // 提取动作并设置安全默认值
                        FString Emotion = JsonObj->HasField(TEXT("emotion")) ? JsonObj->GetStringField(TEXT("emotion")) : TEXT("Normal");
                        FString Action = JsonObj->HasField(TEXT("action")) ? JsonObj->GetStringField(TEXT("action")) : TEXT("Idle");

                        // 广播给动画系统，此时文本还没来，动画先走！
                        OnMetadataReceived.Broadcast(Emotion, Action);
                    }
                }
                // 分支 B：正常文本切片
                else
                {
                    // 恢复后端的换行符转义，保证 UI 可以正常换行
                    FString DisplayToken = Payload.Replace(TEXT("\\n"), TEXT("\n"));
                    // 广播给 UI 显示
                    OnStreamTokenReceived.Broadcast(DisplayToken);
                }
            }
        }
    }
}

void UNPCBrainComponent::OnStreamComplete(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bWasSuccessful)
{
    OnChatCompleted.Broadcast(bWasSuccessful);
}

void UNPCBrainComponent::OnMemoryDistillComplete(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bWasSuccessful)
{
    // 静默执行日志记录
    if (bWasSuccessful) {
        UE_LOG(LogTemp, Log, TEXT("[NPCBrain] 长期记忆已归档"));
    }
}


// Called every frame
//void UNPCBrainComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
//{
//	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
//
//	// ...
//}

void UNPCBrainComponent::SendStreamChatRequest(FString PlayerId, FString NpcId, int32 NpcLevel, FString UserMessage)
{
	ActiveNpcId = NpcId;
    LastParsedStringLength = 0; // 重置游标

    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
    Request->OnRequestProgress64().BindUObject(this, &UNPCBrainComponent::OnStreamProgress);
    Request->OnProcessRequestComplete().BindUObject(this, &UNPCBrainComponent::OnStreamComplete);

    Request->SetURL(ApiBaseUrl + TEXT("/chat_stream"));
    Request->SetVerb("POST");
    Request->SetHeader("Content-Type", "application/json");

    TSharedPtr<FJsonObject> JsonObject = MakeShareable(new FJsonObject());
    JsonObject->SetStringField("world_name", CurrentWorldName);
    JsonObject->SetStringField("npc_name", NpcId);
    JsonObject->SetNumberField("npc_level", NpcLevel);
    JsonObject->SetStringField("player_id", PlayerId);
    JsonObject->SetStringField("player_message", UserMessage);

    FString JsonString;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&JsonString);
    FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);

    Request->SetContentAsString(JsonString);
    Request->ProcessRequest();
}

void UNPCBrainComponent::TriggerMemoryDistillation(FString PlayerId, FString NpcId)
{
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
    Request->OnProcessRequestComplete().BindUObject(this, &UNPCBrainComponent::OnMemoryDistillComplete);
    Request->SetURL(ApiBaseUrl + TEXT("/memory/distill"));
    Request->SetVerb("POST");
    Request->SetHeader("Content-Type", "application/json");

    TSharedPtr<FJsonObject> JsonObject = MakeShareable(new FJsonObject());
    JsonObject->SetStringField("player_id", PlayerId);
    JsonObject->SetStringField("npc_name", NpcId);

    FString JsonString;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&JsonString);
    FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);

    Request->SetContentAsString(JsonString);
    Request->ProcessRequest();
}
//void UNPCBrainComponent::SendChatRequest(FString NpcId, FString UserMessage)
//{
//	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
//	// 绑定http的异步回调
//	Request->OnProcessRequestComplete().BindUObject(this, &UNPCBrainComponent::OnHttpResponseReceived);
//	// 暴露给蓝图的配置
//	Request->SetURL(ApiUrl);
//	Request->SetTimeout(TimeoutSeconds);
//
//	Request->SetVerb("POST");
//	Request->SetHeader("Content-Type", "application/json");
//
//	// 组装JSON请求，注意可以发空请求的
//	TSharedPtr<FJsonObject> JsonObject = MakeShareable(new FJsonObject());
//	JsonObject->SetStringField("npc_id", NpcId);
//	JsonObject->SetStringField("message", UserMessage);
//
//	FString JsonString;
//	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&JsonString);
//	FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);
//
//	Request->SetContentAsString(JsonString);
//
//	Request->ProcessRequest();
//	// TEST
//	UE_LOG(LogTemp, Warning, TEXT("[AI Brain] 正在发送请求... NPC: %s"), *NpcId);
//}

//void UNPCBrainComponent::OnHttpResponseReceived(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bWasSuccessful)
//{
//	if (bWasSuccessful && Response.IsValid()) 
//	{
//		FString ResponseString = Response->GetContentAsString();
//
//		TSharedPtr<FJsonObject> JsonObject;
//		TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(ResponseString);
//
//		if (FJsonSerializer::Deserialize(Reader, JsonObject))
//		{
//			// 处理500/400错误
//			if (JsonObject->HasField("error"))
//			{
//				FString ErrorMsg = JsonObject->GetStringField("error");
//				UE_LOG(LogTemp, Error, TEXT("[AI Brain] 服务器内部错误: %s"), *ErrorMsg);
//				return;
//			}
//			// 提取字段
//			FString Dialogue = JsonObject->GetStringField("dialogue");
//			FString Emotion = JsonObject->GetStringField("emotion");
//			FString Action = JsonObject->GetStringField("action");
//			bool bCallBackup = JsonObject->GetBoolField("call_backup");
//			// TEST
//			UE_LOG(LogTemp, Log, TEXT("[AI Brain] 接收成功！回复: %s, 情绪: %s"), *Dialogue, *Emotion);
//			UE_LOG(LogTemp, Log, TEXT("[AI Brain] 动作: %s, 摇人: %s"), *Action, bCallBackup ? TEXT("True") : TEXT("False"));
//			
//			OnResponseReceived.Broadcast(Dialogue, Emotion, Action, bCallBackup);
//		}
//		else
//		{
//			UE_LOG(LogTemp, Error, TEXT("[AI Brain] JSON 解析失败！"));
//		}
//	}
//	else
//	{
//		UE_LOG(LogTemp, Error, TEXT("[AI Brain] 网络连接失败或超时"));
//	}
//}