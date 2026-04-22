// LeiYure Community


#include "LLM/NPCBrainComponent.h"
#include "Json.h"
#include "JsonUtilities.h"

// Sets default values for this component's properties
UNPCBrainComponent::UNPCBrainComponent()
{
	// 事件驱动，不用每帧tick
	PrimaryComponentTick.bCanEverTick = false;

}


// Called when the game starts
void UNPCBrainComponent::BeginPlay()
{
	Super::BeginPlay();

	// ...
	
}


// Called every frame
void UNPCBrainComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	// ...
}

void UNPCBrainComponent::SendChatRequest(FString NpcId, FString UserMessage)
{
	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
	// 绑定http的异步回调
	Request->OnProcessRequestComplete().BindUObject(this, &UNPCBrainComponent::OnHttpResponseReceived);
	// 暴露给蓝图的配置
	Request->SetURL(ApiUrl);
	Request->SetTimeout(TimeoutSeconds);

	Request->SetVerb("POST");
	Request->SetHeader("Content-Type", "application/json");

	// 组装JSON请求，注意可以发空请求的
	TSharedPtr<FJsonObject> JsonObject = MakeShareable(new FJsonObject());
	JsonObject->SetStringField("npc_id", NpcId);
	JsonObject->SetStringField("message", UserMessage);

	FString JsonString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&JsonString);
	FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);

	Request->SetContentAsString(JsonString);

	Request->ProcessRequest();
	// TEST
	UE_LOG(LogTemp, Warning, TEXT("[AI Brain] 正在发送请求... NPC: %s"), *NpcId);
}

void UNPCBrainComponent::OnHttpResponseReceived(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bWasSuccessful)
{
	if (bWasSuccessful && Response.IsValid()) 
	{
		FString ResponseString = Response->GetContentAsString();

		TSharedPtr<FJsonObject> JsonObject;
		TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(ResponseString);

		if (FJsonSerializer::Deserialize(Reader, JsonObject))
		{
			// 处理500/400错误
			if (JsonObject->HasField("error"))
			{
				FString ErrorMsg = JsonObject->GetStringField("error");
				UE_LOG(LogTemp, Error, TEXT("[AI Brain] 服务器内部错误: %s"), *ErrorMsg);
				return;
			}
			// 提取字段
			FString Dialogue = JsonObject->GetStringField("dialogue");
			FString Emotion = JsonObject->GetStringField("emotion");
			FString Action = JsonObject->GetStringField("action");
			bool bCallBackup = JsonObject->GetBoolField("call_backup");
			// TEST
			UE_LOG(LogTemp, Log, TEXT("[AI Brain] 接收成功！回复: %s, 情绪: %s"), *Dialogue, *Emotion);
			UE_LOG(LogTemp, Log, TEXT("[AI Brain] 动作: %s, 摇人: %s"), *Action, bCallBackup ? TEXT("True") : TEXT("False"));
			
			OnResponseReceived.Broadcast(Dialogue, Emotion, Action, bCallBackup);
		}
		else
		{
			UE_LOG(LogTemp, Error, TEXT("[AI Brain] JSON 解析失败！"));
		}
	}
	else
	{
		UE_LOG(LogTemp, Error, TEXT("[AI Brain] 网络连接失败或超时"));
	}
}