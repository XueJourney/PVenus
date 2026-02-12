import logging
import json
import os
import stat
import base64
import hashlib
from datetime import datetime
from pathlib import Path
import requests
from openai import OpenAI
from PIL import Image
import io
import threading
import tkinter
from tkinter import filedialog

import customtkinter as ctk
import pygame
from pydub import AudioSegment

# --- 外观设置 ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# --- 日志设置 ---
class GuiLogger(logging.Handler):
    """自定义日志处理器，将日志消息重定向到GUI文本框"""
    def __init__(self, textbox):
        super().__init__()
        self.textbox = textbox
        self.textbox.configure(state='disabled')

    def emit(self, record):
        msg = self.format(record)
        def append_msg():
            self.textbox.configure(state='normal')
            self.textbox.insert(tkinter.END, msg + "\n")
            self.textbox.see(tkinter.END)
            self.textbox.configure(state='disabled')
        self.textbox.after(0, append_msg)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# 文件日志处理器
if not os.path.exists('logs'): os.makedirs('logs')
file_handler = logging.FileHandler("logs/app.log", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
# 限制日志文件权限
try:
    os.chmod("logs/app.log", stat.S_IRUSR | stat.S_IWUSR)
except OSError:
    pass


# --- 核心逻辑类 (从CLI版本迁移并适配) ---

class ConfigManager:
    """配置管理类"""
    def __init__(self):
        self.config_dir = "data"
        self.config_file = os.path.join(self.config_dir, "config.json")
        self.memory_file = os.path.join(self.config_dir, "memory.json")
        self.chat_history_file = os.path.join(self.config_dir, "chat_history.json")
        os.makedirs(self.config_dir, exist_ok=True)

    def _secure_write(self, filepath, data):
        """安全写入文件，限制文件权限为仅当前用户可读写"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.chmod(filepath, stat.S_IRUSR | stat.S_IWUSR)  # 600 权限
        except OSError as e:
            logger.error(f"安全写入文件失败 {filepath}: {e}")

    def save_config(self, config):
        """保存配置到本地文件"""
        try:
            self._secure_write(self.config_file, config)
            logger.debug("配置已保存到本地")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")

    def load_config(self):
        """从本地文件加载配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
        return None

    def save_memory(self, memory):
        """保存永久记忆"""
        try:
            self._secure_write(self.memory_file, memory)
            logger.debug("记忆已保存")
        except Exception as e:
            logger.error(f"保存记忆失败: {e}")

    def load_memory(self):
        """加载永久记忆"""
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"加载记忆失败: {e}")
        return {}

    def save_chat_history(self, history):
        """保存聊天记录"""
        try:
            recent_history = history[-20:] if len(history) > 20 else history
            self._secure_write(self.chat_history_file, recent_history)
            logger.debug("聊天记录已保存")
        except Exception as e:
            logger.error(f"保存聊天记录失败: {e}")

    def load_chat_history(self):
        """加载聊天记录"""
        try:
            if os.path.exists(self.chat_history_file):
                with open(self.chat_history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"加载聊天记录失败: {e}")
        return []

class FileProcessor:
    """文件处理类"""
    def __init__(self, siliconflow_key):
        self.siliconflow_key = siliconflow_key
        self.image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}

    def is_image_file(self, file_path):
        """判断是否为图片文件"""
        return Path(file_path).suffix.lower() in self.image_extensions

    def encode_image_to_base64(self, image_path):
        """将图片编码为base64"""
        try:
            file_size = os.path.getsize(image_path)
            if file_size > 20 * 1024 * 1024:  # 20MB 限制
                logger.error(f"图片文件过大 ({file_size} bytes)，最大支持 20MB")
                return None
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"图片编码失败: {e}")
            return None

    def analyze_image(self, image_path):
        """使用Qwen2.5-VL分析图片"""
        try:
            client = OpenAI(
                api_key=self.siliconflow_key,
                base_url="https://api.siliconflow.cn/v1"
            )
            base64_image = self.encode_image_to_base64(image_path)
            if not base64_image:
                return "图片编码失败"
            
            response = client.chat.completions.create(
                model="Qwen/Qwen2.5-VL-72B-Instruct",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}", "detail": "high"}},
                        {"type": "text", "text": "请详细表述这幅图片的内容，包括场景、人物、物品、行为，以及场景可能想要表示的内容。"}
                    ]
                }],
                max_tokens=1000,
                timeout=60
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"图片分析失败: {e}")
            return f"图片分析失败: {str(e)}"

class MemoryManager:
    """记忆管理类"""
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.memory = self.config_manager.load_memory()
        self.next_id = max([int(k) for k in self.memory.keys()] + [0]) + 1

    def add_memory(self, content):
        """添加新记忆"""
        memory_id = str(self.next_id)
        current_time = datetime.now().isoformat()
        self.memory[memory_id] = {"content": content, "created_time": current_time, "last_modified": current_time}
        self.next_id += 1
        self.config_manager.save_memory(self.memory)
        return memory_id

    def delete_memory(self, memory_id):
        """删除记忆"""
        if memory_id in self.memory:
            del self.memory[memory_id]
            self.config_manager.save_memory(self.memory)
            return True
        return False

    def modify_memory(self, memory_id, new_content):
        """修改记忆"""
        if memory_id in self.memory:
            self.memory[memory_id]["content"] = new_content
            self.memory[memory_id]["last_modified"] = datetime.now().isoformat()
            self.config_manager.save_memory(self.memory)
            return True
        return False

    def get_memory_prompt(self):
        """获取记忆提示词"""
        if not self.memory:
            return ""
        memory_text = "永久记忆:\n"
        for mem_id, mem_data in self.memory.items():
            memory_text += f"[{mem_id}] {mem_data['content']} (创建: {mem_data['created_time'][:19]}, 修改: {mem_data['last_modified'][:19]})\n"
        return memory_text

class VoiceManager:
    """语音管理类 (GUI适配版)"""
    def __init__(self, siliconflow_key):
        self.siliconflow_key = siliconflow_key
        self.client = OpenAI(api_key=siliconflow_key, base_url="https://api.siliconflow.cn/v1")
        self.available_voices = {
            "Alex": "FunAudioLLM/CosyVoice2-0.5B:alex", "Anna": "FunAudioLLM/CosyVoice2-0.5B:anna",
            "Bella": "FunAudioLLM/CosyVoice2-0.5B:bella", "Benjamin": "FunAudioLLM/CosyVoice2-0.5B:benjamin",
            "Charles": "FunAudioLLM/CosyVoice2-0.5B:charles", "Claire": "FunAudioLLM/CosyVoice2-0.5B:claire",
            "David": "FunAudioLLM/CosyVoice2-0.5B:david", "Diana": "FunAudioLLM/CosyVoice2-0.5B:diana"
        }
        self.custom_voices = {}
        self.all_voices = {}
        self.selected_voice_uri = self.available_voices["Alex"]

    def refresh_voices(self):
        """获取所有可用音色"""
        self.custom_voices = self._get_custom_voices()
        self.all_voices = {**self.available_voices, **self.custom_voices}
        return list(self.all_voices.keys())

    def _get_custom_voices(self):
        """获取用户自定义音色列表"""
        custom_voices_map = {}
        try:
            response = requests.get("https://api.siliconflow.cn/v1/audio/voice/list", headers={"Authorization": f"Bearer {self.siliconflow_key}"})
            if response.status_code == 200:
                for voice in response.json().get("result", []):
                    if voice.get("uri") and voice.get("customName"):
                        custom_voices_map[voice.get("customName")] = voice.get("uri")
                logger.info(f"成功获取 {len(custom_voices_map)} 个自定义音色")
        except Exception as e:
            logger.error(f"获取自定义音色失败: {e}")
        return custom_voices_map

    def set_voice(self, voice_name):
        """根据名称设置音色"""
        if voice_name in self.all_voices:
            self.selected_voice_uri = self.all_voices[voice_name]
            logger.info(f"音色已切换为: {voice_name}")

    def text_to_speech(self, text, speed=1.0):
        """文本转语音，并支持调速"""
        try:
            output_dir = "data/audio"
            os.makedirs(output_dir, exist_ok=True)
            
            # 使用 时间戳-内容哈希 生成唯一文件名，避免文件冲突
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            content_hash = hashlib.md5(text.encode('utf-8')).hexdigest()[:16]
            base_filename = f"{timestamp}-{content_hash}"
            speech_path = Path(output_dir) / f"{base_filename}.mp3"

            with self.client.audio.speech.with_streaming_response.create(
                model="FunAudioLLM/CosyVoice2-0.5B", voice=self.selected_voice_uri,
                input=text, response_format="mp3"
            ) as response:
                response.stream_to_file(speech_path)

            if speed == 1.0:
                return str(speech_path)
            
            # 使用pydub调速
            sound = AudioSegment.from_mp3(speech_path)
            fast_sound = sound.speedup(playback_speed=speed)
            speed_adjusted_path = Path(output_dir) / f"{base_filename}_x{speed:.1f}.mp3"
            fast_sound.export(speed_adjusted_path, format="mp3")
            logger.info(f"语音已调速至 {speed}x")
            return str(speed_adjusted_path)

        except Exception as e:
            logger.error(f"语音合成失败: {e}")
            return None

class PromptBuilder:
    """提示词构建类 (保持不变)"""
    @staticmethod
    def build_system_prompt():
        return """你是一个智能助手，需要根据用户的偏好和历史记录提供个性化回复。
回复规则：
1. 根据用户的职业、称呼偏好和回复风格调整你的回复
2. 参考永久记忆中的重要信息
3. 考虑最近的聊天历史保持对话连贯性
4. 只有真正重要的信息才需要加入永久记忆
5. 回复要自然、友好、有帮助
记忆操作说明：
- add: 添加新的重要信息到永久记忆
- delete: 删除过时或错误的记忆（提供记忆ID）
- modify: 修改现有记忆内容（提供记忆ID和新内容）"""

    @staticmethod
    def build_user_context(preferences):
        context_parts = []
        if preferences.get('profession') and preferences['profession'] != "None": context_parts.append(f"用户职业: {preferences['profession']}")
        if preferences.get('preferred_title') and preferences['preferred_title'] != "None": context_parts.append(f"称呼用户: {preferences['preferred_title']}")
        if preferences.get('reply_style') and preferences['reply_style'] != "None": context_parts.append(f"回复风格: {preferences['reply_style']}")
        if preferences.get('additional_info') and preferences['additional_info'] != "None": context_parts.append(f"其他信息: {preferences['additional_info']}")
        return "\n".join(context_parts) if context_parts else "用户信息: 暂无特殊偏好"

    @staticmethod
    def build_memory_context(memory_manager):
        if not memory_manager.memory: return "永久记忆: 暂无"
        memory_lines = ["永久记忆:"]
        for mem_id, mem_data in memory_manager.memory.items():
            created = mem_data['created_time'][:19].replace('T', ' ')
            modified = mem_data['last_modified'][:19].replace('T', ' ')
            memory_lines.append(f"[{mem_id}] {mem_data['content']} (创建:{created}, 修改:{modified})")
        return "\n".join(memory_lines)

    @staticmethod
    def build_chat_history_context(chat_history, limit=4):
        if not chat_history: return "聊天历史: 这是第一次对话"
        history_lines = ["最近的聊天记录:"]
        recent_chats = chat_history[-limit:] if len(chat_history) > limit else chat_history
        for i, chat in enumerate(recent_chats, 1):
            history_lines.append(f"{i}. 用户: {chat['user']}")
            history_lines.append(f"   AI: {chat['ai']}")
            history_lines.append("")
        return "\n".join(history_lines)

    @staticmethod
    def build_json_format_instruction():
        return """请严格按照以下JSON格式回复：
{
    "response": "展现给用户的回复内容，要自然友好，符合用户偏好",
    "memory_operations": [
        {"action": "add/delete/modify", "id": "记忆ID(删除和修改时必需)", "content": "记忆内容(添加和修改时必需)"}
    ]
}"""

    @classmethod
    def build_complete_prompt(cls, user_input, preferences, memory_manager, chat_history):
        current_time = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
        prompt_parts = [
            cls.build_system_prompt(), "", f"当前时间: {current_time}", "",
            cls.build_user_context(preferences), "", cls.build_memory_context(memory_manager), "",
            cls.build_chat_history_context(chat_history), "", f"用户当前输入: {user_input}", "",
            cls.build_json_format_instruction()
        ]
        return "\n".join(prompt_parts)


# --- GUI 主应用 ---

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PVenus GUI")
        self.geometry("1200x800")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 初始化
        pygame.mixer.init()
        self.config_manager = ConfigManager()
        self.memory_manager = MemoryManager(self.config_manager)
        self.openai_client = None
        self.file_processor = None
        self.voice_manager = None
        self.chat_history = []
        self.attached_file_path = None
        self.chat_bubbles = [] # 用于存储所有消息气泡以更新换行
        
        # 创建组件
        self.create_widgets()
        self.setup_gui_logger()
        
        # 加载配置
        self.after(100, self.load_and_initialize)
        self.bind("<Configure>", self.on_chat_resize) # 绑定窗口大小调整事件

    def create_widgets(self):
        # ... UI布局 ...
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=4)
        self.grid_rowconfigure(0, weight=1)

        # -- 左侧控制面板 --
        self.left_frame = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nsew")
        self.left_frame.grid_rowconfigure(1, weight=0) # Settings frame
        self.left_frame.grid_rowconfigure(6, weight=1) # Log frame
        
        # 语音模块
        self.voice_frame = ctk.CTkFrame(self.left_frame)
        self.voice_frame.grid(row=0, column=0, padx=10, pady=10, sticky="new")
        self.voice_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self.voice_frame, text="语音选项").grid(row=0, column=0, columnspan=2, padx=10, pady=(10,5))
        
        self.voice_enabled_switch = ctk.CTkSwitch(self.voice_frame, text="语音回复", command=self.toggle_voice_enabled)
        self.voice_enabled_switch.grid(row=1, column=0, columnspan=2, padx=10, pady=5)
        
        self.voice_selector = ctk.CTkComboBox(self.voice_frame, values=["-"], command=self.on_voice_selected, state="disabled")
        self.voice_selector.grid(row=2, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

        self.speed_slider = ctk.CTkSlider(self.voice_frame, from_=0.5, to=2.0, command=self.update_speed_label)
        self.speed_slider.set(1.0)
        self.speed_slider.grid(row=3, column=0, padx=(10,5), pady=10, sticky="ew")
        self.speed_label = ctk.CTkLabel(self.voice_frame, text="语速: 1.0x")
        self.speed_label.grid(row=3, column=1, padx=(0,10), pady=10)

        self.play_pause_button = ctk.CTkButton(self.voice_frame, text="▶ 播放", command=self.toggle_playback, state="disabled")
        self.play_pause_button.grid(row=4, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        
        # 设置模块
        self.settings_frame = ctk.CTkFrame(self.left_frame)
        self.settings_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.settings_button = ctk.CTkButton(self.settings_frame, text="打开设置", command=self.open_settings_window)
        self.settings_button.pack(fill="x", padx=10, pady=10)

        # -- 右侧聊天面板 --
        self.right_frame = ctk.CTkFrame(self, corner_radius=0)
        self.right_frame.grid(row=0, column=1, sticky="nsew")
        self.right_frame.grid_rowconfigure(0, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)

        self.chat_box = ctk.CTkScrollableFrame(self.right_frame, label_text="对话")
        self.chat_box.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        self.input_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.input_frame.grid(row=1, column=0, padx=10, pady=10, sticky="sew")
        self.input_frame.grid_columnconfigure(1, weight=1)
        
        self.attach_button = ctk.CTkButton(self.input_frame, text="📎", width=30, command=self.attach_file)
        self.attach_button.grid(row=0, column=0, padx=(0,5))

        self.user_input = ctk.CTkEntry(self.input_frame, placeholder_text="输入消息...")
        self.user_input.grid(row=0, column=1, sticky="ew")
        self.user_input.bind("<Return>", self.send_message)
        
        self.send_button = ctk.CTkButton(self.input_frame, text="发送", width=60, command=self.send_message)
        self.send_button.grid(row=0, column=2, padx=(5,0))

    def setup_gui_logger(self):
        # 日志输出框
        log_frame = ctk.CTkFrame(self.left_frame)
        log_frame.grid(row=6, column=0, padx=10, pady=10, sticky="nsew")
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(log_frame, text="日志输出").grid(row=0, column=0, padx=10, pady=5)
        
        log_textbox = ctk.CTkTextbox(log_frame, wrap=tkinter.WORD)
        log_textbox.grid(row=1, column=0, padx=10, pady=(0,10), sticky="nsew")
        
        gui_handler = GuiLogger(log_textbox)
        gui_handler.setFormatter(formatter)
        logger.addHandler(gui_handler)

    # ... 其他方法 ...

    def load_and_initialize(self):
        """加载配置并初始化客户端"""
        config = self.config_manager.load_config()
        if not config or not config.get('siliconflow_key') or not config.get('openai_key'):
            logger.warning("未找到有效配置，需要用户输入。")
            self.open_settings_window(is_initial_setup=True)
            return

        self.setup_clients(config)
        self.load_chat_history()

    def open_settings_window(self, is_initial_setup=False):
        """打开设置窗口，用于输入API Keys和用户偏好。"""
        if hasattr(self, 'settings_window') and self.settings_window.winfo_exists():
            self.settings_window.focus()
            return

        self.settings_window = ctk.CTkToplevel(self)
        self.settings_window.title("设置")
        self.settings_window.geometry("550x580")
        self.settings_window.transient(self)
        self.settings_window.grab_set()

        # 加载现有配置
        current_config = self.config_manager.load_config() or {}
        current_prefs = current_config.get('preferences', {})

        # --- API 设置 ---
        api_frame = ctk.CTkFrame(self.settings_window)
        api_frame.pack(fill="x", padx=15, pady=15)
        api_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(api_frame, text="API 设置", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, pady=(0,10))

        ctk.CTkLabel(api_frame, text="SiliconFlow Key:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        sf_key_entry = ctk.CTkEntry(api_frame, show="*")
        sf_key_entry.grid(row=1, column=1, sticky="ew", padx=10, pady=5)
        sf_key_entry.insert(0, current_config.get("siliconflow_key", ""))

        ctk.CTkLabel(api_frame, text="OpenAI Key:").grid(row=2, column=0, sticky="w", padx=10, pady=5)
        oai_key_entry = ctk.CTkEntry(api_frame, show="*")
        oai_key_entry.grid(row=2, column=1, sticky="ew", padx=10, pady=5)
        oai_key_entry.insert(0, current_config.get("openai_key", ""))

        ctk.CTkLabel(api_frame, text="OpenAI Gateway:").grid(row=3, column=0, sticky="w", padx=10, pady=5)
        oai_gw_entry = ctk.CTkEntry(api_frame)
        oai_gw_entry.grid(row=3, column=1, sticky="ew", padx=10, pady=5)
        oai_gw_entry.insert(0, current_config.get("openai_api_gateway", "https://api.openai.com/v1"))

        # --- 用户偏好设置 ---
        prefs_frame = ctk.CTkFrame(self.settings_window)
        prefs_frame.pack(fill="x", padx=15, pady=(0, 15))
        prefs_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(prefs_frame, text="用户偏好", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, pady=(0,10))

        ctk.CTkLabel(prefs_frame, text="您的职业:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        profession_entry = ctk.CTkEntry(prefs_frame)
        profession_entry.grid(row=1, column=1, sticky="ew", padx=10, pady=5)
        profession_entry.insert(0, current_prefs.get("profession", "None"))

        ctk.CTkLabel(prefs_frame, text="希望如何称呼您:").grid(row=2, column=0, sticky="w", padx=10, pady=5)
        title_entry = ctk.CTkEntry(prefs_frame)
        title_entry.grid(row=2, column=1, sticky="ew", padx=10, pady=5)
        title_entry.insert(0, current_prefs.get("preferred_title", "None"))

        ctk.CTkLabel(prefs_frame, text="AI回复风格:").grid(row=3, column=0, sticky="w", padx=10, pady=5)
        style_entry = ctk.CTkEntry(prefs_frame)
        style_entry.grid(row=3, column=1, sticky="ew", padx=10, pady=5)
        style_entry.insert(0, current_prefs.get("reply_style", "None"))
        
        ctk.CTkLabel(prefs_frame, text="其他补充信息:").grid(row=4, column=0, sticky="w", padx=10, pady=5)
        info_entry = ctk.CTkTextbox(prefs_frame, height=80)
        info_entry.grid(row=5, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        info_entry.insert("1.0", current_prefs.get("additional_info", "None"))
        
        def save_and_close():
            new_config = {
                "siliconflow_key": sf_key_entry.get(),
                "openai_key": oai_key_entry.get(),
                "openai_api_gateway": oai_gw_entry.get(),
                "preferences": {
                    "profession": profession_entry.get(),
                    "preferred_title": title_entry.get(),
                    "reply_style": style_entry.get(),
                    "additional_info": info_entry.get("1.0", "end-1c")
                }
            }
            self.config_manager.save_config(new_config)
            logger.info("配置已保存，正在重新初始化客户端...")
            self.setup_clients(new_config)
            self.settings_window.destroy()

        # --- 保存按钮 ---
        save_button = ctk.CTkButton(self.settings_window, text="保存并应用", command=save_and_close)
        save_button.pack(pady=15)
        
        if is_initial_setup:
            self.settings_window.protocol("WM_DELETE_WINDOW", self.destroy) # 首次设置时关闭窗口则退出程序

    def setup_clients(self, config):
        """根据配置设置API客户端"""
        sf_key = config.get('siliconflow_key')
        oai_key = config.get('openai_key')
        oai_gw = config.get('openai_api_gateway', "https://api.openai.com/v1")

        if not sf_key or not oai_key:
            logger.error("API Keys不完整，客户端初始化失败。")
            return

        self.file_processor = FileProcessor(sf_key)
        self.voice_manager = VoiceManager(sf_key)
        self.openai_client = OpenAI(api_key=oai_key, base_url=oai_gw)
        
        logger.info("API客户端初始化成功。")
        self.refresh_voice_list()
        
    def refresh_voice_list(self):
        """刷新音色下拉列表"""
        if self.voice_manager:
            voices = self.voice_manager.refresh_voices()
            self.voice_selector.configure(values=voices, state="normal")
            if voices:
                self.voice_selector.set(voices[0])
                self.voice_manager.set_voice(voices[0])

    def on_voice_selected(self, choice):
        if self.voice_manager:
            self.voice_manager.set_voice(choice)

    def toggle_voice_enabled(self):
        is_enabled = self.voice_enabled_switch.get() == 1
        logger.info(f"语音回复已 {'启用' if is_enabled else '关闭'}")
        
    def update_speed_label(self, value):
        self.speed_label.configure(text=f"语速: {float(value):.1f}x")

    def attach_file(self):
        filepath = filedialog.askopenfilename()
        if filepath:
            self.attached_file_path = filepath
            filename = os.path.basename(filepath)
            self.user_input.delete(0, tkinter.END)
            self.user_input.insert(0, f"文件: {filename}")
            logger.info(f"已附加文件: {filepath}")

    def send_message(self, event=None):
        user_text = self.user_input.get().strip()
        if not user_text and not self.attached_file_path:
            return

        self.add_message_to_chatbox("您", user_text)
        self.user_input.delete(0, tkinter.END)
        self.set_input_state("disabled")

        thread = threading.Thread(target=self._send_message_thread, args=(user_text, self.attached_file_path))
        thread.daemon = True
        thread.start()
        self.attached_file_path = None

    def _send_message_thread(self, user_text, file_path):
        """处理消息的后台线程"""
        try:
            processed_input = user_text
            if file_path:
                if self.file_processor.is_image_file(file_path):
                    self.after(0, lambda: self.add_message_to_chatbox("系统", "正在分析图片..."))
                    logger.info(f"开始分析图片: {file_path}")
                    analysis = self.file_processor.analyze_image(file_path)
                    logger.info("图片分析完成。")
                    processed_input += f"\n\n[图片分析结果 ({os.path.basename(file_path)})]:\n{analysis}"
                else:
                    processed_input += f"\n\n[附加文件: {os.path.basename(file_path)}]"

            logger.info("开始构建完整的提示词...")
            prompt = PromptBuilder.build_complete_prompt(
                processed_input,
                self.config_manager.load_config().get('preferences', {}),
                self.memory_manager,
                self.chat_history
            )
            logger.debug(f"构建的提示词长度: {len(prompt)} 字符")

            request_payload = {
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "max_tokens": 2000
            }
            logger.debug(f"请求模型: {request_payload['model']}, max_tokens: {request_payload['max_tokens']}")

            logger.info("正在向 OpenAI 发送请求...")
            response = self.openai_client.chat.completions.create(
                **request_payload, timeout=120
            )
            logger.info("已收到 OpenAI 的回复。")
            ai_response_text = response.choices[0].message.content
            logger.debug(f"收到 OpenAI 回复，长度: {len(ai_response_text)} 字符")

            self.after(0, self.process_ai_response, ai_response_text, user_text)
        except Exception as e:
            logger.error(f"消息处理线程出错: {e}", exc_info=True)
            self.after(0, lambda: self.add_message_to_chatbox("错误", "处理消息时出错，请查看日志。"))
            self.after(0, self.set_input_state, "normal")


    def process_ai_response(self, ai_response_text, original_user_input):
        """处理并显示AI的回复"""
        try:
            logger.debug(f"开始处理AI回复JSON，长度: {len(ai_response_text)} 字符")
            response_data = json.loads(ai_response_text)
            display_response = response_data.get("response", "AI回复格式错误，请检查日志。")

            # 记忆操作
            memory_ops = response_data.get("memory_operations", [])
            if memory_ops:
                logger.info(f"检测到 {len(memory_ops)} 个记忆操作。")
                for op in memory_ops:
                    action = op.get("action")
                    op_id = op.get("id")
                    op_content = op.get("content")
                    logger.info(f"执行操作: action={action}, id={op_id}, content='{op_content[:50] if op_content else 'N/A'}...'")
                    if action == "add": self.memory_manager.add_memory(op['content'])
                    elif action == "delete": self.memory_manager.delete_memory(op['id'])
                    elif action == "modify": self.memory_manager.modify_memory(op['id'], op['content'])
            
            self.add_message_to_chatbox("AI", display_response)
            
            self.chat_history.append({"user": original_user_input, "ai": display_response, "timestamp": datetime.now().isoformat()})
            self.config_manager.save_chat_history(self.chat_history)
            
            if self.voice_enabled_switch.get() == 1 and self.voice_manager:
                logger.info("语音回复已启用，开始生成语音。")
                self.generate_and_play_speech(display_response)
            else:
                self.set_input_state("normal")

        except json.JSONDecodeError:
            logger.error(f"AI回复JSON解析失败: {ai_response_text}")
            self.add_message_to_chatbox("AI", ai_response_text) # 直接显示原始文本
            self.set_input_state("normal")
        except Exception as e:
            logger.error(f"处理AI回复时出错: {e}", exc_info=True)
            self.set_input_state("normal")


    def generate_and_play_speech(self, text):
        """生成并播放语音"""
        def task():
            speed = self.speed_slider.get()
            voice_file = self.voice_manager.text_to_speech(text, speed)
            if voice_file:
                self.after(0, self.play_audio, voice_file)
            else:
                self.after(0, self.set_input_state, "normal")
        
        thread = threading.Thread(target=task)
        thread.daemon = True
        thread.start()

    def play_audio(self, filepath):
        """用pygame播放音频"""
        try:
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            self.play_pause_button.configure(text="❚❚ 暂停", state="normal")
            self.check_music_status()
        except pygame.error as e:
            logger.error(f"播放音频失败: {e}")
            self.set_input_state("normal")
    
    def check_music_status(self):
        """检查音乐播放是否结束"""
        if pygame.mixer.music.get_busy():
            self.after(100, self.check_music_status)
        else:
            self.play_pause_button.configure(text="▶ 播放", state="disabled")
            self.set_input_state("normal")

    def toggle_playback(self):
        """切换播放/暂停状态"""
        if pygame.mixer.music.get_busy():
            if pygame.mixer.music.get_pos() > 0: # Is playing
                pygame.mixer.music.pause()
                self.play_pause_button.configure(text="▶ 播放")
            else: # Is paused
                pygame.mixer.music.unpause()
                self.play_pause_button.configure(text="❚❚ 暂停")

    def add_message_to_chatbox(self, sender, message):
        """向聊天框添加一条消息"""
        is_user = sender == "您"
        
        # 为每条消息创建一个容器，该容器占满整行宽度
        row_frame = ctk.CTkFrame(self.chat_box, fg_color="transparent")
        row_frame.pack(fill="x", padx=5, pady=2)

        # 消息气泡本身
        bubble_frame = ctk.CTkFrame(
            row_frame,
            corner_radius=10,
            fg_color=("#dcdcdc", "#333333") if is_user else ("#efefef", "#2b2b2b")
        )
        
        # 使用 grid 来对齐气泡
        if is_user:
            # 用户消息，右对齐
            row_frame.grid_columnconfigure(0, weight=1) # 左侧空白伸缩
            row_frame.grid_columnconfigure(1, weight=0)
            bubble_frame.grid(row=0, column=1, sticky="e", padx=(50, 0)) # 增加左边距，使其不会占满全宽
        else:
            # AI消息，左对齐
            row_frame.grid_columnconfigure(0, weight=0)
            row_frame.grid_columnconfigure(1, weight=1) # 右侧空白伸缩
            bubble_frame.grid(row=0, column=0, sticky="w", padx=(0, 50)) # 增加右边距

        # 发送者标签
        label = ctk.CTkLabel(bubble_frame, text=f"{sender}:", font=ctk.CTkFont(weight="bold"))
        label.pack(anchor="w", padx=10, pady=(5, 0))
        
        # 消息内容
        # 初始加载时winfo_width可能不准，因此先给一个较大的默认值
        wraplen = self.chat_box.winfo_width() - 80
        if wraplen < 100:
            wraplen = self.winfo_width() * 0.5 # 如果chat_box宽度无效，则根据主窗口估算

        msg_bubble = ctk.CTkLabel(
            bubble_frame, text=message, wraplength=wraplen,
            justify="left"
        )
        msg_bubble.pack(anchor="w", fill="x", padx=10, pady=(0, 5))
        self.chat_bubbles.append(msg_bubble) # 将消息标签添加到列表中以便后续更新
        
        # 滚动到底部
        self.chat_box._parent_canvas.after(100, lambda: self.chat_box._parent_canvas.yview_moveto(1.0))

    def load_chat_history(self):
        """加载并显示聊天记录"""
        self.chat_history = self.config_manager.load_chat_history()
        for chat in self.chat_history:
            self.add_message_to_chatbox("您", chat['user'])
            self.add_message_to_chatbox("AI", chat['ai'])
        logger.info(f"成功加载 {len(self.chat_history)} 条聊天记录")

    def set_input_state(self, state="normal"):
        """设置输入相关组件的状态"""
        self.user_input.configure(state=state)
        self.send_button.configure(state=state)
        self.attach_button.configure(state=state)

    def on_closing(self):
        """关闭程序时的处理"""
        logger.info("程序正在关闭...")
        pygame.mixer.quit()
        self.destroy()

    def on_chat_resize(self, event=None):
        """当窗口或聊天框大小改变时，更新消息气泡的换行宽度"""
        # 减去各种内边距，并留出一些空间，确保文本不会紧贴边缘
        wraplen = self.chat_box.winfo_width() - 80 
        if wraplen > 100: # 只有在宽度有效时才更新
            for bubble in self.chat_bubbles:
                bubble.configure(wraplength=wraplen)

if __name__ == "__main__":
    app = App()
    app.mainloop()
