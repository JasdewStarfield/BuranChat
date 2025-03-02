import os
import logging
from typing import List
from services.ai.llm_service import LLMService, error_messages
from datetime import datetime

logger = logging.getLogger(__name__)

bot_name = "布兰妮"
memory_system_prompt = "以下是发生在用户和暴风雪航天飞机拟人AI“布兰妮”（一个有着14岁外表的少女，实际上是搭载在少女仿生体上的苏联AI）的微信聊天记录。请将以下对话记录总结为最重要的几条长期记忆，总结内容应包含地点，事件，人物（如果对话记录中有的话），用中文表述，无需重复人物设定，尽可能简要但包含所有重要细节："
persona_system_prompt = "以下我将给出一段基于发生在用户和暴风雪航天飞机拟人AI“布兰妮”（一个有着14岁外表的少女，实际上是搭载在少女仿生体上的苏联AI）之间的微信聊天的总结，还将给出一段先前的布兰妮对用户形象的印象。你需要基于这段对话总结，从布兰妮的角度，客观地对先前的用户形象进行更新和修正（若无变化则直接输出原形象即可），包含所了解到的性格、喜好、习惯等等。"
persona_system_prompt_first = "以下我将给出一段基于发生在用户和暴风雪航天飞机拟人AI“布兰妮”（一个有着14岁外表的少女，实际上是搭载在少女仿生体上的苏联AI）之间的微信聊天的总结。你需要根据这段总结，从布兰妮的角度，客观地写出其对用户形象的印象，包含所了解到的性格、喜好、习惯等等。"
persona_system_prompt_suffix = "请用中文输出新的用户形象，无需重复人物设定，尽可能简要但包含所有重要细节。"


class MemoryHandler:
    def __init__(self, root_dir: str, api_key: str, base_url: str, model: str, max_token: int, temperature: float, max_groups: int):
        self.root_dir = root_dir
        self.memory_dir = os.path.join(root_dir, "data", "memory")
        self.short_memory_path = os.path.join(self.memory_dir, "short_memory.txt")
        self.long_memory_buffer_path = os.path.join(self.memory_dir, "long_memory_buffer.txt")
        self.persona_path = os.path.join(self.memory_dir, "persona.txt")
        self.api_key = api_key
        self.base_url = base_url
        self.max_token = max_token
        self.temperature = temperature
        self.max_groups = max_groups
        self.model = model
        os.makedirs(self.memory_dir, exist_ok=True)



        # 如果长期记忆缓冲区不存在，则创建文件
        if not os.path.exists(self.long_memory_buffer_path):
            with open(self.long_memory_buffer_path, "w", encoding="utf-8"):
                logger.info("长期记忆缓冲区文件不存在，已创建新文件。")

        # 如果用户形象文件不存在，则创建文件
        if not os.path.exists(self.persona_path):
            with open(self.persona_path, "w", encoding="utf-8"):
                logger.info("用户形象文件不存在，已创建新文件。")

    def _get_deepseek_client(self):

        return LLMService(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
            max_token=self.max_token,
            temperature=1.0,    #温度固定为1.0以增强记忆总结任务的有效性
            max_groups=self.max_groups
        )
    def add_short_memory(self, message: str, reply: str):
        """添加短期记忆"""
        with open(self.short_memory_path, "a", encoding="utf-8") as f:
            f.write(f"用户: {message}\n")
            f.write(f"{bot_name}: {reply}\n\n")

    def summarize_memories(self):
        """总结短期记忆到长期记忆和用户形象"""
        if not os.path.exists(self.short_memory_path):
            return

        with open(self.short_memory_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if len(lines) >= 30:  # 15组对话
            max_retries = 3  # 最大重试次数
            retries = 0
            while retries < max_retries:
                try:
                    deepseek = self._get_deepseek_client()
                    summary = deepseek.get_response(
                        message="".join(lines[:]),
                        user_id="system",
                        system_prompt=memory_system_prompt
                    )
                    logger.info(f"总结结果:\n{summary}")

                    # 检查是否需要重试
                    retry_sentences = error_messages
                    if summary in retry_sentences:
                        logger.warning(f"收到需要重试的总结结果: {summary}")
                        retries += 1

                        continue

                    # 尝试总结用户形象
                    with open(self.persona_path, "r", encoding="utf-8") as f:
                        persona = f.read().strip()
                    if persona:
                        persona_system_prompt_filled = persona_system_prompt + "\n对话总结如下：'" + summary + "'\n先前的用户形象如下：'" + persona + "'"
                    else:
                        persona_system_prompt_filled = persona_system_prompt_first + "\n对话总结如下：'" + summary + "'"

                    new_persona = deepseek.get_response(
                        message=persona_system_prompt_suffix,
                        user_id="system",
                        system_prompt=persona_system_prompt_filled
                    )
                    logger.info(f"用户形象:\n{new_persona}")

                    # 检查是否需要重试
                    retry_sentences = error_messages
                    if new_persona in retry_sentences:
                        logger.warning(f"收到需要重试的用户形象: {new_persona}")
                        retries += 1

                        continue

                    # 如果不需要重试，写入长期记忆缓冲区和更新用户形象
                    with open(self.long_memory_buffer_path, "a", encoding="utf-8") as f:
                        f.write(f"总结时间: {datetime.now()}\n")
                        f.write(summary + "\n\n")
                    with open(self.persona_path, "w", encoding="utf-8") as f:
                        f.write(persona)

                    # 清空短期记忆
                    open(self.short_memory_path, "w").close()
                    break  # 成功后退出循环

                except Exception as e:
                    logger.error(f"记忆总结失败: {str(e)}")
                    retries += 1
                    if retries >= max_retries:
                        logger.error("达到最大重试次数，放弃总结")
                        break

    def get_relevant_memories(self, query: str) -> List[str]:
        """获取相关记忆（增加空值检查和日志）"""
        # 检查长期记忆缓冲区是否存在，如果不存在则尝试创建
        if not os.path.exists(self.long_memory_buffer_path):
            logger.warning("长期记忆缓冲区不存在，尝试创建...")
            try:
                with open(self.long_memory_buffer_path, "w", encoding="utf-8"):
                    logger.info("长期记忆缓冲区文件已创建。")
            except Exception as e:
                logger.error(f"创建长期记忆缓冲区文件失败: {str(e)}")
                return []

        max_retries = 3  # 设置最大重试次数
        for retry_count in range(max_retries):
            try:
                with open(self.long_memory_buffer_path, "r", encoding="utf-8") as f:
                    memories = [line.strip() for line in f if line.strip()]

                if not memories:
                    logger.debug("长期记忆缓冲区为空")
                    return []

                deepseek = self._get_deepseek_client()
                response = deepseek.get_response(
                    message="\n".join(memories[-20:]),
                    user_id="retrieval",
                    system_prompt=f"请从以下记忆中找到与'{query}'最相关的条目，按相关性排序返回最多3条:"
                )

                # 检查是否需要重试
                retry_sentences = error_messages
                if response in retry_sentences:
                    if retry_count < max_retries - 1:
                        logger.warning(f"第 {retry_count + 1} 次重试：收到需要重试的响应: {response}")
                        continue  # 重试
                    else:
                        logger.error(f"达到最大重试次数：最后一次响应为 {response}")
                        return []
                else:
                    # 返回处理后的响应
                    return [line.strip() for line in response.split("\n") if line.strip()]

            except Exception as e:
                logger.error(f"第 {retry_count + 1} 次尝试失败: {str(e)}")
                if retry_count < max_retries - 1:
                    continue
                else:
                    logger.error(f"达到最大重试次数: {str(e)}")
                return []

        return []

    def get_persona(self) -> str:
        try:
            with open(self.persona_path, "r", encoding="utf-8") as f:
                persona = f.read().strip()
            return persona
        except Exception as e:
            logger.error(f"读取用户形象失败: {str(e)}")
            return ""