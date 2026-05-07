import os
import io
import base64
import tempfile
import subprocess
from openai import AsyncOpenAI
from langchain_community.document_loaders import PyPDFLoader, TextLoader

# 测试，逻辑待完善
class MediaETLFactory:
    """
    ETL 流水线：将所有转化为 LLM 能懂的文本和图片信息的逻辑都封装在这里
    """
    def __init__(self):
        # 复用云端配置，使用 Whisper 模型进行语音转文字
        self.audio_client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL") 
        )

    async def process(self, file_bytes: bytes, file_name: str, mime_type: str) -> tuple[str, list]:
        """
        智能路由分发，返回 (解析后的文本内容, base64图片列表)
        """
        # 文本/文档
        if mime_type in ["text/plain", "application/pdf"]:
            text = await self._process_document(file_bytes, file_name)
            return text, []

        # 纯图片
        elif mime_type.startswith("image/"):
            b64_image = base64.b64encode(file_bytes).decode('utf-8')
            return "【用户在本次交互中附带了一张图片】", [f"data:{mime_type};base64,{b64_image}"]

        # 纯音频
        elif mime_type.startswith("audio/"):
            text = await self._process_audio(file_bytes, file_name)
            return f"【用户音频转写内容】：\n{text}", []

        # 视频通道 (音轨分离 + 关键帧抽帧)
        elif mime_type.startswith("video/"):
            text, frame_b64 = await self._process_video(file_bytes, file_name)
            return f"【视频抽离语音转写内容】：\n{text}", [f"data:image/jpeg;base64,{frame_b64}"]

        else:
            raise ValueError(f"系统尚未接入 {mime_type} 类型的解析策略")

    # ==================== 具体策略实现 ====================

    async def _process_document(self, file_bytes: bytes, file_name: str) -> str:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file_name}") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        try:
            if file_name.endswith(".pdf"):
                docs = PyPDFLoader(tmp_path).load()
            else:
                docs = TextLoader(tmp_path, encoding='utf-8').load()
            text = "\n".join([doc.page_content for doc in docs])
            return text[:15000] + ("\n...[截断]" if len(text) > 15000 else "")
        finally:
            os.remove(tmp_path)

    async def _process_audio(self, file_bytes: bytes, file_name: str) -> str:
        """
        TODO: 逻辑和视频一样也待完善
        调用 Whisper API 将语音转为文本，qwen的语音模型暂时不支持openai
        """
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        try:
            with open(tmp_path, "rb") as audio_file:
                # 调用标准 OpenAI Whisper 接口
                transcript = await self.audio_client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio_file
                )
            return transcript.text
        except Exception as e:
            return f"【系统提示：当前大模型服务暂未启用语音解析功能，请使用文字描述。内部信息：{str(e)}】"
        finally:
            os.remove(tmp_path)

    async def _process_video(self, file_bytes: bytes, file_name: str) -> tuple[str, str]:
        """
        TODO: FFmpeg 视频处理流水线待完善，filename用来获取后缀
        FFmpeg 提取视频信息
        1. 抽离声音转文字
        2. 抽取中间的一帧画面当封面
        """
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_video:
            tmp_video.write(file_bytes)
            video_path = tmp_video.name
            
        audio_path = video_path + ".mp3"
        frame_path = video_path + ".jpg"

        try:
            # 暂时没有FFmpeg环境，保底直接返回提示文本和空画面
            try:
                subprocess.run(['ffmpeg', '-i', video_path, '-q:a', '0', '-map', 'a', audio_path, '-y'], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                subprocess.run(['ffmpeg', '-i', video_path, '-ss', '00:00:01', '-vframes', '1', frame_path, '-y'], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            except (FileNotFoundError, subprocess.CalledProcessError) as e:
                return f"（系统未配置 FFmpeg 或抽帧失败，无法解析视频画面与音轨。提示：{str(e)}）", ""

            # 解析音频
            transcript_text = "（视频无声音或提取失败）"
            if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                with open(audio_path, "rb") as af:
                    transcript = await self.audio_client.audio.transcriptions.create(model="whisper-1", file=af)
                    transcript_text = transcript.text

            # 解析画面
            frame_b64 = ""
            if os.path.exists(frame_path):
                with open(frame_path, "rb") as img:
                    frame_b64 = base64.b64encode(img.read()).decode('utf-8')

            return transcript_text, frame_b64
        finally:
            for p in [video_path, audio_path, frame_path]:
                if os.path.exists(p):
                    os.remove(p)