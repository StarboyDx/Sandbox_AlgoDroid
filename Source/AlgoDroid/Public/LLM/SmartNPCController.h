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

	/*virtual void OnPossess(APawn* InPawn) override;*/

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AI Components")
	UNPCBrainComponent* LLMBrain;

	UFUNCTION(BlueprintCallable, Category = "AI Interaction")
	void StartTalkiing(FString PlayerMessage);

protected:
	virtual void BeginPlay() override;

	//UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AI Brain")
	//UNPCBrainComponent* LLMBrain;

	/*UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AI Brain")
	TObjectPtr<UNPCBrainComponent> LLMBrain;*/

	/*FString ActiveNpcId;*/
};
