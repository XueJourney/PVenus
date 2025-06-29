import logging
import json
import os
import base64
from datetime import datetime
from pathlib import Path
import requests
from openai import OpenAI
from PIL import Image
import io

# 创建一个 Logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# 创建文件Handler，保存为 UTF-8 编码，等级为 DEBUG
file_handler = logging.FileHandler("app.log", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)

# 创建控制台Handler，等级为 INFO
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# 设置日志格式
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# 给两个Handler都设置格式
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# 添加Handler到Logger中
logger.addHandler(file_handler)
logger.addHandler(console_handler)

class ConfigManager:
    """配置管理类"""
    def __init__(self):
        self.config_file = "config.json"
        self.memory_file = "memory.json"
        self.chat_history_file = "chat_history.json"
    
    def save_config(self, config):
        """保存配置到本地文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
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
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(memory, f, ensure_ascii=False, indent=2)
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
            # 只保存最新的8条记录
            recent_history = history[-8:] if len(history) > 8 else history
            with open(self.chat_history_file, 'w', encoding='utf-8') as f:
                json.dump(recent_history, f, ensure_ascii=False, indent=2)
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
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail":"high"
                                }
                            },
                            {"type": "text", "text": "请详细表述这幅图片的内容，包括场景、人物、物品、行为，以及场景可能想要表示的内容。"}
                        ]
                    }
                ],
                max_tokens=1000
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
        self.memory[memory_id] = {
            "content": content,
            "created_time": current_time,
            "last_modified": current_time
        }
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
    """语音管理类"""
    def __init__(self, siliconflow_key):
        self.siliconflow_key = siliconflow_key
        self.client = OpenAI(
            api_key=siliconflow_key,
            base_url="https://api.siliconflow.cn/v1"
        )
        self.available_voices = {
            "1": "FunAudioLLM/CosyVoice2-0.5B:alex",
            "2": "FunAudioLLM/CosyVoice2-0.5B:anna",
            "3": "FunAudioLLM/CosyVoice2-0.5B:bella",
            "4": "FunAudioLLM/CosyVoice2-0.5B:benjamin",
            "5": "FunAudioLLM/CosyVoice2-0.5B:charles",
            "6": "FunAudioLLM/CosyVoice2-0.5B:claire",
            "7": "FunAudioLLM/CosyVoice2-0.5B:david",
            "8": "FunAudioLLM/CosyVoice2-0.5B:diana"
        }
        self.custom_voices = self.get_custom_voices()
        self.selected_voice = "FunAudioLLM/CosyVoice2-0.5B:alex"
    
    def get_custom_voices(self):
        """获取用户自定义音色列表"""
        try:
            import requests
            response = requests.get(
                "https://api.siliconflow.cn/v1/audio/voice/list",
                headers={"Authorization": f"Bearer {self.siliconflow_key}"}
            )
            if response.status_code == 200:
                logger.debug(response.json())
                # 提取uri列表
                info = []
                for i in response.json().get("result", []):
                    if i.get("uri"):
                        info.append(i)
                return info
        except Exception as e:
            logger.error(f"获取自定义音色失败: {e}")
        return []
    
    def show_voice_options(self):
        """显示音色选择菜单"""
        print("\n=== 音色选择 ===")
        print("预设音色:")
        for key, voice in self.available_voices.items():
            mark = " ✓" if voice == self.selected_voice else ""
            print(f"{key}. {voice}{mark}")
        
        if self.custom_voices:
            print("\n自定义音色:")
            for i, voice in enumerate(self.custom_voices, start=len(self.available_voices)+1):
                mark = " ✓" if voice.get("uri") == self.selected_voice else ""
                print(f"{i}. {voice.get('customName', 'Unknown')}{mark}")
        
        print(f"\n当前选择: {self.selected_voice}")
        print("================")
    
    def select_voice(self):
        """选择音色"""
        self.show_voice_options()
        
        try:
            choice = input("\n请选择音色编号 (直接回车保持当前选择): ").strip()
            if not choice:
                return
            
            if choice in self.available_voices:
                self.selected_voice = self.available_voices[choice]
                print(f"已选择音色: {self.selected_voice}")
            elif choice.isdigit():
                choice_idx = int(choice) - len(self.available_voices) - 1
                if 0 <= choice_idx < len(self.custom_voices):
                    self.selected_voice = self.custom_voices[choice_idx]["uri"]
                    print(f"已选择自定义音色: {self.custom_voices[choice_idx]['customName']}")
                else:
                    print("无效选择")
            else:
                print("无效选择")
        except Exception as e:
            logger.error(f"选择音色时出错: {e}")
            print("选择音色失败")
    
    def text_to_speech(self, text, output_file="output.mp3"):
        """文本转语音"""
        try:
            speech_file_path = Path(output_file)
            
            with self.client.audio.speech.with_streaming_response.create(
                model="FunAudioLLM/CosyVoice2-0.5B",
                voice=self.selected_voice,
                input=text,
                response_format="mp3"
            ) as response:
                response.stream_to_file(speech_file_path)
            
            return str(speech_file_path)
        except Exception as e:
            logger.error(f"语音合成失败: {e}")
            return None

class PromptBuilder:
    """提示词构建类"""
    
    @staticmethod
    def build_system_prompt():
        """构建系统提示词"""
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
- modify: 修改现有记忆内容（提供记忆ID和新内容）
"""
    
    @staticmethod
    def build_user_context(preferences):
        """构建用户上下文信息"""
        context_parts = []
        
        if preferences.get('profession') and preferences['profession'] != "None":
            context_parts.append(f"用户职业: {preferences['profession']}")
        
        if preferences.get('preferred_title') and preferences['preferred_title'] != "None":
            context_parts.append(f"称呼用户: {preferences['preferred_title']}")
        
        if preferences.get('reply_style') and preferences['reply_style'] != "None":
            context_parts.append(f"回复风格: {preferences['reply_style']}")
        
        if preferences.get('additional_info') and preferences['additional_info'] != "None":
            context_parts.append(f"其他信息: {preferences['additional_info']}")
        
        return "\n".join(context_parts) if context_parts else "用户信息: 暂无特殊偏好"
    
    @staticmethod
    def build_memory_context(memory_manager):
        """构建记忆上下文"""
        if not memory_manager.memory:
            return "永久记忆: 暂无"
        
        memory_lines = ["永久记忆:"]
        for mem_id, mem_data in memory_manager.memory.items():
            created = mem_data['created_time'][:19].replace('T', ' ')
            modified = mem_data['last_modified'][:19].replace('T', ' ')
            memory_lines.append(f"[{mem_id}] {mem_data['content']} (创建:{created}, 修改:{modified})")
        
        return "\n".join(memory_lines)
    
    @staticmethod
    def build_chat_history_context(chat_history, limit=4):
        """构建聊天历史上下文"""
        if not chat_history:
            return "聊天历史: 这是第一次对话"
        
        history_lines = ["最近的聊天记录:"]
        recent_chats = chat_history[-limit:] if len(chat_history) > limit else chat_history
        
        for i, chat in enumerate(recent_chats, 1):
            history_lines.append(f"{i}. 用户: {chat['user']}")
            history_lines.append(f"   AI: {chat['ai']}")
            history_lines.append("")
        
        return "\n".join(history_lines)
    
    @staticmethod
    def build_json_format_instruction():
        """构建JSON格式说明"""
        return """请严格按照以下JSON格式回复：
{
    "response": "展现给用户的回复内容，要自然友好，符合用户偏好",
    "memory_operations": [
        {
            "action": "add/delete/modify",
            "id": "记忆ID(删除和修改时必需，添加时不需要)",
            "content": "记忆内容(添加和修改时必需，删除时不需要)"
        }
    ]
}

重要提醒：
- response字段是直接展示给用户的内容，要完整、自然
- memory_operations数组包含对永久记忆的操作，非必需时可以为空数组
- 只有真正重要、需要长期记住的信息才进行记忆操作
- 删除记忆时只需要提供action和id
- 修改记忆时需要提供action、id和新的content
- 添加记忆时只需要提供action和content"""
    
    @classmethod
    def build_complete_prompt(cls, user_input, preferences, memory_manager, chat_history):
        """构建完整的提示词"""
        current_time = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
        
        prompt_parts = [
            cls.build_system_prompt(),
            "",
            f"当前时间: {current_time}",
            "",
            cls.build_user_context(preferences),
            "",
            cls.build_memory_context(memory_manager),
            "",
            cls.build_chat_history_context(chat_history),
            "",
            f"用户当前输入: {user_input}",
            "",
            cls.build_json_format_instruction()
        ]
        
        return "\n".join(prompt_parts)

class AIChat:
    """AI聊天主类"""
    def __init__(self):
        self.config_manager = ConfigManager()
        self.memory_manager = MemoryManager(self.config_manager)
        self.file_processor = None
        self.voice_manager = None
        self.openai_client = None
        self.chat_history = self.config_manager.load_chat_history()
        self.voice_enabled = False
    
    def initialize_config(self):
        """初始化配置"""
        logger.info("初始化中...")
        logger.info("获取配置信息...")
        
        # 尝试加载已保存的配置
        saved_config = self.config_manager.load_config()
        if saved_config:
            print("发现已保存的配置:")
            print(f"SiliconFlow Key: {'*' * (len(saved_config['siliconflow_key']) - 4) + saved_config['siliconflow_key'][-4:]}")
            print(f"OpenAI Key: {'*' * (len(saved_config['openai_key']) - 4) + saved_config['openai_key'][-4:]}")
            print(f"API网关: {saved_config['openai_api_gateway']}")
            
            use_saved = input("是否使用已保存的配置？(y/n): ").strip().lower()
            if use_saved == 'y':
                return saved_config
        
        # 获取新配置
        siliconflow_key = input("请输入siliconflow的key：").strip()
        openai_key = input("请输入openai的key：").strip()
        openai_api_gateway = input("请输入openai的API网关(空则默认官方)：").strip()
        if openai_api_gateway == "":
            openai_api_gateway = "https://api.openai.com/v1"

        preferences = {
            'profession': input("您的职业：").strip() or "None",
            'preferred_title': input("您喜欢的称呼：").strip() or "None",
            'reply_style': input("您希望AI如何回复：").strip() or "None",
            'additional_info': input("AI还需要知道的其他信息：").strip() or "None",
            'last_updated': datetime.now().isoformat()
        }
        
        config = {
            'siliconflow_key': siliconflow_key,
            'openai_key': openai_key,
            'openai_api_gateway': openai_api_gateway,
            'preferences': preferences
        }
        
        # 保存配置
        self.config_manager.save_config(config)
        return config
    
    def setup_clients(self, config):
        """设置API客户端"""
        self.file_processor = FileProcessor(config['siliconflow_key'])
        self.voice_manager = VoiceManager(config['siliconflow_key'])
        self.openai_client = OpenAI(
            api_key=config['openai_key'],
            base_url=config['openai_api_gateway']
        )
    
    def parse_user_input(self, user_input):
        """解析用户输入，检查是否包含文件路径"""
        words = user_input.split()
        files_info = []
        text_input = user_input
        
        for word in words:
            # 检查绝对路径和相对路径
            if os.path.exists(word):
                if self.file_processor.is_image_file(word):
                    logger.info(f"检测到图片文件: {word}")
                    image_analysis = self.file_processor.analyze_image(word)
                    files_info.append(f"图片分析结果({word}): {image_analysis}")
                else:
                    logger.info(f"检测到非图片文件: {word}")
        
        if files_info:
            text_input = user_input + "\n\n" + "\n".join(files_info)
        
        return text_input
    
    def process_ai_response(self, ai_response_text):
        """处理AI的JSON回复"""
        try:
            ai_response = json.loads(ai_response_text)
            
            # 处理记忆操作
            if "memory_operations" in ai_response:
                for operation in ai_response["memory_operations"]:
                    action = operation.get("action")
                    if action == "add":
                        memory_id = self.memory_manager.add_memory(operation["content"])
                        logger.info(f"添加记忆 [{memory_id}]: {operation['content']}")
                    elif action == "delete":
                        if self.memory_manager.delete_memory(operation["id"]):
                            logger.info(f"删除记忆 [{operation['id']}]")
                    elif action == "modify":
                        if self.memory_manager.modify_memory(operation["id"], operation["content"]):
                            logger.info(f"修改记忆 [{operation['id']}]: {operation['content']}")
            
            return ai_response.get("response", "AI回复格式错误")
            
        except json.JSONDecodeError:
            logger.error("AI回复不是有效的JSON格式")
            return ai_response_text
        except Exception as e:
            logger.error(f"处理AI回复时出错: {e}")
            return ai_response_text
    
    def show_menu(self):
        """显示菜单"""
        print("\n=== 菜单选项 ===")
        print("1. 继续对话")
        print("2. 查看记忆")
        print("3. 清空聊天记录")
        print("4. 启用/关闭语音回复")
        print("5. 选择语音音色")
        print("6. 退出程序")
        print("================")
    
    def show_memory(self):
        """显示所有记忆"""
        if not self.memory_manager.memory:
            print("暂无永久记忆")
            return
        
        print("\n=== 永久记忆 ===")
        for mem_id, mem_data in self.memory_manager.memory.items():
            print(f"[{mem_id}] {mem_data['content']}")
            print(f"    创建: {mem_data['created_time'][:19]}")
            print(f"    修改: {mem_data['last_modified'][:19]}")
            print()
    
    def clear_chat_history(self):
        """清空聊天记录"""
        self.chat_history = []
        self.config_manager.save_chat_history(self.chat_history)
        print("聊天记录已清空")
    
    def toggle_voice(self):
        """切换语音功能"""
        self.voice_enabled = not self.voice_enabled
        status = "已启用" if self.voice_enabled else "已关闭"
        print(f"语音回复{status}")
    
    def run(self):
        """运行主程序"""
        try:
            # 初始化配置
            config = self.initialize_config()
            self.setup_clients(config)
            
            logger.info("程序初始化完成")
            print("\n欢迎使用AI聊天助手！")
            print("您可以直接输入消息开始对话，或输入 '/menu' 查看菜单选项")
            print("支持在消息中包含图片路径，AI会自动分析图片内容")
            
            while True:
                try:
                    user_input = input("\n您: ").strip()
                    
                    if not user_input:
                        continue
                    
                    # 菜单命令
                    if user_input == "/menu":
                        self.show_menu()
                        choice = input("请选择选项 (1-6): ").strip()
                        if choice == "1":
                            continue
                        elif choice == "2":
                            self.show_memory()
                        elif choice == "3":
                            self.clear_chat_history()
                        elif choice == "4":
                            self.toggle_voice()
                        elif choice == "5":
                            if self.voice_manager:
                                self.voice_manager.select_voice()
                            else:
                                print("语音功能未初始化")
                        elif choice == "6":
                            print("再见！")
                            break
                        else:
                            print("无效选项")
                        continue
                    
                    # 解析用户输入（检查文件）
                    processed_input = self.parse_user_input(user_input)
                    
                    # 构建提示词
                    prompt = PromptBuilder.build_complete_prompt(
                        processed_input, 
                        config['preferences'], 
                        self.memory_manager, 
                        self.chat_history
                    )
                    
                    # 调用OpenAI API
                    logger.debug("正在调用OpenAI API...")
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": prompt}],
                        response_format={"type": "json_object"},
                        max_tokens=2000
                    )
                    
                    ai_response_text = response.choices[0].message.content
                    
                    # 处理AI回复
                    display_response = self.process_ai_response(ai_response_text)
                    
                    print(f"\nAI: {display_response}")
                    
                    # 保存聊天记录
                    self.chat_history.append({
                        "user": user_input,
                        "ai": display_response,
                        "timestamp": datetime.now().isoformat()
                    })
                    self.config_manager.save_chat_history(self.chat_history)
                    
                    # 语音输出
                    if self.voice_enabled and self.voice_manager:
                        logger.info("正在生成语音...")
                        voice_file = self.voice_manager.text_to_speech(display_response)
                        if voice_file:
                            print(f"语音文件已生成: {voice_file}")
                            print(f"当前音色: {self.voice_manager.selected_voice}")
                    
                except KeyboardInterrupt:
                    print("\n\n程序被用户中断")
                    break
                except Exception as e:
                    logger.error(f"处理用户输入时出错: {e}")
                    print(f"出现错误: {e}")
                    
        except Exception as e:
            logger.error(f"程序运行出错: {e}")
            print(f"程序出现严重错误: {e}")

def main():
    chat = AIChat()
    chat.run()

if __name__ == "__main__":
    main()