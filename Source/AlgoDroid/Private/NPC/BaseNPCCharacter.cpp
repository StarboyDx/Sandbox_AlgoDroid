// LeiYure Community


#include "NPC/BaseNPCCharacter.h"

// Sets default values
ABaseNPCCharacter::ABaseNPCCharacter()
{
 	// Set this character to call Tick() every frame.  You can turn this off to improve performance if you don't need it.
	PrimaryActorTick.bCanEverTick = true;

}

// Called when the game starts or when spawned
void ABaseNPCCharacter::BeginPlay()
{
	Super::BeginPlay();
	
}

// Called every frame
void ABaseNPCCharacter::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

}

// Called to bind functionality to input
void ABaseNPCCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);

}

