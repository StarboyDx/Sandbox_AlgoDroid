// LeiYure Community

#pragma once

#include "CoreMinimal.h"
#include "AIController.h"
#include "NPCBrainComponent.h"
#include "SmartNPCController.generated.h"

/**
 * 
 */
UCLASS()
class ALGODROID_API ASmartNPCController : public AAIController
{
	GENERATED_BODY()
	
public:

	ASmartNPCController();

	virtual void OnPossess(APawn* InPawn) override;

	UFUNCTION(BlueprintCallable, Category = "AI")
	void StartTalkiing(FString PlayerMessage);

protected:

	//UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AI Brain")
	//UNPCBrainComponent* LLMBrain;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AI Brain")
	TObjectPtr<UNPCBrainComponent> LLMBrain;

	FString ActiveNpcId;
};
