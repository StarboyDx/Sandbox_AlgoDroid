// LeiYure Community

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Http.h"
#include "NPCBrainComponent.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_FourParams(FOnNPCResponseReceived, const FString&, Dialogue, const FString&, Emotion, const FString&, Action, bool, bCallBackup);

UCLASS( ClassGroup=(Custom), meta=(BlueprintSpawnableComponent) )
class ALGODROID_API UNPCBrainComponent : public UActorComponent
{
	GENERATED_BODY()

public:	

	UNPCBrainComponent();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AI Config")
	FString ApiUrl = TEXT("http://127.0.0.1:5000/chat");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AI Config")
	float TimeoutSeconds = 30.0f;

	UFUNCTION(BlueprintCallable, Category = "AI Brain")
	void SendChatRequest(FString NpcId, FString UserMessage);

	UPROPERTY(BlueprintAssignable, Category = "AI Brain")
	FOnNPCResponseReceived OnResponseReceived;

protected:

	virtual void BeginPlay() override;

public:	

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	void OnHttpResponseReceived(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bWasSuccessful);
};
