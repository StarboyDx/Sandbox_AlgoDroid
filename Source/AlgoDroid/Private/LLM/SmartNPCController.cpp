// LeiYure Community


#include "LLM/SmartNPCController.h"
#include "NPC/BaseNPCCharacter.h"

ASmartNPCController::ASmartNPCController()
{
	LLMBrain = CreateDefaultSubobject<UNPCBrainComponent>(TEXT("NPCBrainComponent"));
}

//void ASmartNPCController::OnPossess(APawn* InPawn)
//{
//	Super::OnPossess(InPawn);
//
//	if (ABaseNPCCharacter* NPC = Cast<ABaseNPCCharacter>(InPawn))
//	{
//		ActiveNpcId = NPC->NpcId;
//		// TEST LOG
//		UE_LOG(LogTemp, Warning, TEXT("[Controller] 身份已锁定为: %s"), *ActiveNpcId);
//	}
//	else
//	{
//		// TESE LOG
//		UE_LOG(LogTemp, Error, TEXT("[Controller] 绑定类型错误！"));
//	}
//}

void ASmartNPCController::StartTalkiing(FString PlayerMessage)
{
	if (!LLMBrain) return;

	// 获取当前控制器附身的 Pawn（也就是那个小白人）
	if (ABaseNPCCharacter* NPCBody = Cast<ABaseNPCCharacter>(GetPawn()))
	{
		// 从身体上扒下身份信息（你在编辑器面板里填的 ID）
		FString NpcId = NPCBody->NpcId;
		int32 Level = NPCBody->NpcLevel;

		// 玩家身份标识
		FString PlayerId = TEXT("test_player_001");

		// 调用大脑组件发起请求
		LLMBrain->SendStreamChatRequest(PlayerId, NpcId, Level, PlayerMessage);
	}
	else
	{
		UE_LOG(LogTemp, Error, TEXT("控制器没有附身在 BaseNPCCharacter 上！"));
	}
	//if (ActiveNpcId.IsEmpty())
	//{
	//	if (ABaseNPCCharacter* NPC = Cast<ABaseNPCCharacter>(GetPawn()))
	//	{
	//		ActiveNpcId = NPC->NpcId;
	//		UE_LOG(LogTemp, Warning, TEXT("[Controller] 重新锁定身份: %s"), *ActiveNpcId);
	//	}
	//}
	//if (LLMBrain && !ActiveNpcId.IsEmpty())
	//{
	//	// TEST LOG
	//	UE_LOG(LogTemp, Log, TEXT("[Controller] 当前角色 %s ..."), *ActiveNpcId);

	//	LLMBrain->SendChatRequest(ActiveNpcId, PlayerMessage);
	//}
	//else
	//{
	//	UE_LOG(LogTemp, Error, TEXT("[Controller] 未就绪 or 没有读取到身份！"));
	//}
}

void ASmartNPCController::BeginPlay()
{
	Super::BeginPlay();
}
