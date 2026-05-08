// LeiYure Community

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Http.h"
#include "NPCBrainComponent.generated.h"

// DECLARE_DYNAMIC_MULTICAST_DELEGATE_FourParams(FOnNPCResponseReceived, const FString&, Dialogue, const FString&, Emotion, const FString&, Action, bool, bCallBackup);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnChatStreamTokenReceived, const FString&, Token);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnChatCompleted, bool, bWasSuccessful);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnMetadataReceived, const FString&, Emotion, const FString&, Action);

UCLASS( ClassGroup=(Custom), meta=(BlueprintSpawnableComponent) )
class ALGODROID_API UNPCBrainComponent : public UActorComponent
{
	GENERATED_BODY()

public:	

	UNPCBrainComponent();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AI Config")
	FString ApiBaseUrl = TEXT("http://127.0.0.1:8000/api/v1");
	// FString ApiUrl = TEXT("http://127.0.0.1:5000/chat"); demo

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AI Config")
	FString CurrentWorldName = TEXT("Valoria");

	// 发起对话
	UFUNCTION(BlueprintCallable, Category = "AI Logic")
	void SendStreamChatRequest(FString PlayerId, FString NpcId, int32 NpcLevel, FString UserMessage);
	// 长期记忆提取
	UFUNCTION(BlueprintCallable, Category = "AI Logic")
	void TriggerMemoryDistillation(FString PlayerId, FString NpcId);

	// 监听的事件
	UPROPERTY(BlueprintAssignable, Category = "AI Events")
	FOnChatStreamTokenReceived OnStreamTokenReceived;

	UPROPERTY(BlueprintAssignable, Category = "AI Events")
	FOnChatCompleted OnChatCompleted;

	UPROPERTY(BlueprintAssignable, Category = "AI Events")
	FOnMetadataReceived OnMetadataReceived;

	/*UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AI Config")
	float TimeoutSeconds = 30.0f;*/

	// 留档非流式对话的接口
	/*UFUNCTION(BlueprintCallable, Category = "AI Brain")
	void SendChatRequest(FString NpcId, FString UserMessage);*/

	/*UPROPERTY(BlueprintAssignable, Category = "AI Brain")
	FOnNPCResponseReceived OnResponseReceived;*/

protected:

	virtual void BeginPlay() override;

public:	
	// 流式网络回调
	void OnStreamProgress(FHttpRequestPtr Request, uint64 BytesSent, uint64 BytesReceived);
	void OnStreamComplete(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bWasSuccessful);

	// 记忆提炼网络回调
	void OnMemoryDistillComplete(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bWasSuccessful);

	// 用于安全解析流式中文字符的状态变量
	int32 LastParsedStringLength;

	// 缓存当前正在对话的 NPC ID，方便报错时溯源
	FString ActiveNpcId;

	// 同样也是之前的处理函数留档
	/*virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	void OnHttpResponseReceived(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bWasSuccessful);*/
};
