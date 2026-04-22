// LeiYure Community

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "BaseNPCCharacter.generated.h"

UCLASS()
class ALGODROID_API ABaseNPCCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	// Sets default values for this character's properties
	ABaseNPCCharacter();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AI Identity")
	FString NpcId;

protected:
	// Called when the game starts or when spawned
	virtual void BeginPlay() override;

public:	
	// Called every frame
	virtual void Tick(float DeltaTime) override;

	// Called to bind functionality to input
	virtual void SetupPlayerInputComponent(class UInputComponent* PlayerInputComponent) override;

};
