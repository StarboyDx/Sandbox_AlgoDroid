// LeiYure Community


#include "LLM/SmartNPCController.h"
#include "NPC/BaseNPCCharacter.h"

ASmartNPCController::ASmartNPCController()
{
	LLMBrain = CreateDefaultSubobject<UNPCBrainComponent>(TEXT("NPCBrainComponent"));
}

void ASmartNPCController::OnPossess(APawn* InPawn)
{
	Super::OnPossess(InPawn);

	if (ABaseNPCCharacter* NPC = Cast<ABaseNPCCharacter>(InPawn))
	{
		ActiveNpcId = NPC->NpcId;
		// TEST LOG
		UE_LOG(LogTemp, Warning, TEXT("[Controller] 身份已锁定为: %s"), *ActiveNpcId);
	}
	else
	{
		// TESE LOG
		UE_LOG(LogTemp, Error, TEXT("[Controller] 绑定类型错误！"));
	}
}

void ASmartNPCController::StartTalkiing(FString PlayerMessage)
{
	if (LLMBrain && !ActiveNpcId.IsEmpty())
	{
		// TEST LOG
		UE_LOG(LogTemp, Log, TEXT("[Controller] 当前角色 %s ..."), *ActiveNpcId);

		LLMBrain->SendChatRequest(ActiveNpcId, PlayerMessage);
	}
	else
	{
		UE_LOG(LogTemp, Error, TEXT("[Controller] 未就绪 or 没有读取到身份！"));
	}
}
