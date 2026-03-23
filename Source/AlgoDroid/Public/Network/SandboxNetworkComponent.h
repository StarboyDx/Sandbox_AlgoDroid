// LeiYure Community

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Sockets.h"
#include "SocketSubsystem.h"
#include "Interfaces/IPv4/IPv4Address.h"
#include "SandboxNetworkComponent.generated.h"


UCLASS( ClassGroup=(Custom), meta=(BlueprintSpawnableComponent) )
class ALGODROID_API USandboxNetworkComponent : public UActorComponent
{
	GENERATED_BODY()

public:	
	// Sets default values for this component's properties
	USandboxNetworkComponent();

protected:
	// Called when the game starts
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

public:	
	// Called every frame
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	// 暴露给蓝图调用的连接函数
	UFUNCTION(BlueprintCallable, Category = "AlgoNetwork")
	bool ConnectToPythonBrain(FString IPAddress, int32 Port);

	// 发送数据的接口
	UFUNCTION(BlueprintCallable, Category = "AlgoNetwork")
	bool SendData(FString DataToSend);

	UFUNCTION(BlueprintCallable, Category = "AlgoNetwork")
	void RequestSlidingWindow(const TArray<int32>& RadarData);

private:
	FSocket* ClientSocket;
};
