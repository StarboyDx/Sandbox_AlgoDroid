// LeiYure Community


#include "Network/SandboxNetworkComponent.h"

// Sets default values for this component's properties
USandboxNetworkComponent::USandboxNetworkComponent()
{
	// Set this component to be initialized when the game starts, and to be ticked every frame.  You can turn these features
	// off to improve performance if you don't need them.
	PrimaryComponentTick.bCanEverTick = true;
	ClientSocket = nullptr;

}


// Called when the game starts
void USandboxNetworkComponent::BeginPlay()
{
	Super::BeginPlay();

	// ...
	
}

void USandboxNetworkComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	Super::EndPlay(EndPlayReason);
	// 游戏结束时清理 Socket，防止内存泄漏或端口占用
	if (ClientSocket)
	{
		ClientSocket->Close();
		ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->DestroySocket(ClientSocket);
		ClientSocket = nullptr;
	}
}

// Called every frame
void USandboxNetworkComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	
	if (!ClientSocket || ClientSocket->GetConnectionState() != SCS_Connected) return;

	uint32 Size;
	// 用 while 循环，确保当前帧把缓冲区里的所有数据读完
	while (ClientSocket->HasPendingData(Size))
	{
		TArray<uint8> ReceivedData;
		ReceivedData.SetNumUninitialized(Size);
		int32 BytesRead = 0;

		// 读取数据
		if (ClientSocket->Recv(ReceivedData.GetData(), ReceivedData.Num(), BytesRead))
		{
			// 将接收到的 UTF-8 字节流转换为 UE 的 FString
			ReceivedData.Add(0); // 添加字符串结束符 \0，防止乱码
			FString ReceivedString = FString(UTF8_TO_TCHAR(ReceivedData.GetData()));

			// 粗略验证：直接在屏幕和日志打印原始 JSON 字符串
			UE_LOG(LogTemp, Warning, TEXT("[From Python Brain]: %s"), *ReceivedString);
			if (GEngine)
			{
				GEngine->AddOnScreenDebugMessage(-1, 5.f, FColor::Green, FString::Printf(TEXT("Received: %s"), *ReceivedString));
			}

			// 解析 JSON (将字符串还原为变量)
			TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(ReceivedString);
			TSharedPtr<FJsonObject> JsonObject;

			if (FJsonSerializer::Deserialize(Reader, JsonObject) && JsonObject.IsValid())
			{
				// 读取在 Python 端定好的 status 字段
				FString Status;
				if (JsonObject->TryGetStringField(TEXT("status"), Status) && Status == TEXT("success"))
				{
					int32 BestStart = JsonObject->GetIntegerField(TEXT("best_start"));
					int32 MaxLength = JsonObject->GetIntegerField(TEXT("max_length"));

					// 粗略验证
					UE_LOG(LogTemp, Error, TEXT("Bingo! Algorithm Solved! Move Drone to index: %d, width is: %d"), BestStart, MaxLength);

					// 也可以打印在屏幕上方便查看
					if (GEngine)
					{
						GEngine->AddOnScreenDebugMessage(-1, 5.f, FColor::Red, FString::Printf(TEXT("Parsed BestStart: %d, MaxLength: %d"), BestStart, MaxLength));
					}
				}
			}
		}
	}

}

bool USandboxNetworkComponent::ConnectToPythonBrain(FString IPAddress, int32 Port)
{
	FIPv4Address IPv4Address;
	FIPv4Address::Parse(IPAddress, IPv4Address);

	TSharedRef<FInternetAddr> Addr = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->CreateInternetAddr();
	Addr->SetIp(IPv4Address.Value);
	Addr->SetPort(Port);

	//NAME_Stream = TCP
	ClientSocket = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->CreateSocket(NAME_Stream, TEXT("PythonBrainSocket"), false);
	bool bConnected = ClientSocket->Connect(*Addr);

	if (bConnected)
	{
		UE_LOG(LogTemp, Warning, TEXT("Successfully connected to Python Brain!"));
	}
	else
	{
		UE_LOG(LogTemp, Error, TEXT("Failed to connect to Python Brain."));
	}

	return bConnected;
}

bool USandboxNetworkComponent::SendData(FString DataToSend)
{
	if (!ClientSocket || ClientSocket->GetConnectionState() != SCS_Connected) return false;

	// UE 的 FString 是 TCHAR，网络传输需要转换成 UTF-8 字节流
	FTCHARToUTF8 Convert(*DataToSend);
	int32 BytesSent = 0;
	bool bSuccessful = ClientSocket->Send((uint8*)Convert.Get(), Convert.Length(), BytesSent);

	return bSuccessful;
}

void USandboxNetworkComponent::RequestSlidingWindow(const TArray<int32>& RadarData)
{
	// 创建 JSON 对象并打包数据 (业务逻辑)
	TSharedPtr<FJsonObject> RootObject = MakeShareable(new FJsonObject());
	RootObject->SetStringField(TEXT("action"), TEXT("sliding_window"));

	TSharedPtr<FJsonObject> PayloadObject = MakeShareable(new FJsonObject());
	TArray<TSharedPtr<FJsonValue>> JsonRadarArray;
	for (int32 Val : RadarData)
	{
		JsonRadarArray.Add(MakeShareable(new FJsonValueNumber(Val)));
	}
	PayloadObject->SetArrayField(TEXT("radar"), JsonRadarArray);
	RootObject->SetObjectField(TEXT("payload"), PayloadObject);

	// 序列化成字符串
	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(RootObject.ToSharedRef(), Writer);

	// 加上换行符，然后【直接调用底层的 SendData】发出去！
	OutputString += TEXT("\n");

	if (SendData(OutputString))
	{
		UE_LOG(LogTemp, Log, TEXT("Successfully routed to SendData: %s"), *OutputString);
	}
}
