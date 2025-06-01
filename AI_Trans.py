import os
import srt
import tkinter as tk
from tkinter import ttk, scrolledtext
from srt import parse, compose
import tkinter.messagebox as messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
import threading
import queue
import requests
import json
import ollama
import time
import re

# 如果需要自动检测文件编码，请安装：pip install charset-normalizer

class SRTTranslatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SRT字幕翻译工具2.0-Sky繁星")
        self.root.geometry("800x600")  # 增加窗口大小
        
        # 创建消息队列用于线程间通信
        self.message_queue = queue.Queue()
        self.translation_thread = None
        self.stop_translation = False
        
        # 状态标签
        self.status_label = ttk.Label(root, text="正在检查Ollama服务...", font=('微软雅黑', 10))
        self.status_label.pack(pady=5)
        
        # 拖放区域
        self.drop_frame = tk.Frame(root, bd=2, relief="groove")
        self.drop_frame.pack(pady=10, padx=20, fill="both", expand=True)
        self.drop_label = tk.Label(self.drop_frame, text="将SRT文件拖放到此处", font=('微软雅黑', 12))
        self.drop_label.pack(expand=True, fill="both")
        # 绑定拖放事件
        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind('<<Drop>>', self.on_drop)

        # 语言选择框架
        self.lang_frame = tk.Frame(root)
        self.lang_frame.pack(pady=10, padx=20, fill="x")

        # 原语言下拉框
        self.src_lang_label = ttk.Label(self.lang_frame, text="原语言：")
        self.src_lang_label.grid(row=0, column=0, padx=5, sticky="w")
        self.src_lang = ttk.Combobox(self.lang_frame, values=["英语", "日语", "中文"], state="readonly")
        self.src_lang.grid(row=0, column=1, padx=5, sticky="ew")
        self.src_lang.current(0)  # 默认英语
        self.src_lang.bind('<<ComboboxSelected>>', self.update_dest_lang)

        # 目标语言下拉框
        self.dest_lang_label = ttk.Label(self.lang_frame, text="目标语言：")
        self.dest_lang_label.grid(row=1, column=0, padx=5, pady=10, sticky="w")
        self.dest_lang = ttk.Combobox(self.lang_frame, values=["中文", "英语", "日语"], state="readonly")
        self.dest_lang.grid(row=1, column=1, padx=5, pady=10, sticky="ew")
        self.update_dest_lang()

        # Ollama模型选择
        self.model_label = ttk.Label(self.lang_frame, text="Ollama模型：")
        self.model_label.grid(row=2, column=0, padx=5, pady=10, sticky="w")
        self.model_combo = ttk.Combobox(self.lang_frame, state="readonly")
        self.model_combo.grid(row=2, column=1, padx=5, pady=10, sticky="ew")

        # 使用翻译模型复选框
        self.use_translate_model = tk.BooleanVar(value=False)
        self.translate_model_check = ttk.Checkbutton(
            self.lang_frame, 
            text="使用专用翻译模型", 
            variable=self.use_translate_model,
            command=self.toggle_translate_model
        )
        self.translate_model_check.grid(row=2, column=2, padx=5, pady=10)

        # Ollama API地址
        self.api_label = ttk.Label(self.lang_frame, text="API地址：")
        self.api_label.grid(row=3, column=0, padx=5, pady=10, sticky="w")
        self.api_entry = ttk.Entry(self.lang_frame)
        self.api_entry.grid(row=3, column=1, padx=5, pady=10, sticky="ew")
        self.api_entry.insert(0, "http://localhost:11434")

        # 刷新模型按钮
        self.refresh_btn = ttk.Button(self.lang_frame, text="刷新模型列表", command=self.refresh_models)
        self.refresh_btn.grid(row=3, column=2, padx=5, pady=10)

        self.lang_frame.grid_columnconfigure(1, weight=1)

        # 按钮框架
        self.button_frame = tk.Frame(root)
        self.button_frame.pack(pady=10, fill="x")
        
        # 开始按钮
        self.start_btn = ttk.Button(self.button_frame, text="开始翻译", command=self.start_translation)
        self.start_btn.pack(side="left", padx=5)
        
        # 中止按钮
        self.stop_btn = ttk.Button(self.button_frame, text="中止翻译", command=self.stop_translation_process, state="disabled")
        self.stop_btn.pack(side="left", padx=5)

        # 进度框架
        self.progress_frame = tk.Frame(root)
        self.progress_frame.pack(pady=10, padx=20, fill="x")
        
        # 进度条
        self.progress_bar = ttk.Progressbar(self.progress_frame, orient="horizontal", length=400, mode="determinate")
        self.progress_bar.pack(side="left", fill="x", expand=True)
        
        # 翻译预览文本框
        self.preview_text = scrolledtext.ScrolledText(self.progress_frame, height=6, width=40, wrap=tk.WORD)
        self.preview_text.pack(side="left", padx=10, fill="both", expand=True)
        
        # 初始化时禁用所有控件
        self.disable_controls()
        
        # 启动时检查Ollama服务并获取模型列表
        threading.Thread(target=self.initialize_ollama, daemon=True).start()
        
        # 定期检查消息队列
        self.root.after(100, self.check_message_queue)

    def initialize_ollama(self):
        """初始化Ollama服务检查并获取模型列表"""
        try:
            # 检查Ollama服务是否运行
            api_url = self.api_entry.get().strip()
            response = requests.get(f"{api_url}/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [model["name"] for model in models]
                if model_names:
                    self.message_queue.put({
                        "type": "update_models",
                        "models": model_names
                    })
                    self.message_queue.put({
                        "type": "status",
                        "text": "就绪"
                    })
                    self.enable_controls()
                else:
                    self.message_queue.put({
                        "type": "error",
                        "text": "未找到可用的Ollama模型，请先下载模型"
                    })
            else:
                self.message_queue.put({
                    "type": "error",
                    "text": "Ollama服务未运行或无法访问"
                })
        except Exception as e:
            self.message_queue.put({
                "type": "error",
                "text": f"连接Ollama服务失败: {str(e)}"
            })

    def refresh_models(self):
        """刷新模型列表"""
        self.disable_controls()
        self.message_queue.put({
            "type": "status",
            "text": "正在刷新模型列表..."
        })
        threading.Thread(target=self.initialize_ollama, daemon=True).start()

    def check_message_queue(self):
        try:
            while True:
                message = self.message_queue.get_nowait()
                if message["type"] == "progress":
                    self.progress_bar["value"] = message["value"]
                elif message["type"] == "status":
                    self.status_label.config(text=message["text"])
                elif message["type"] == "complete":
                    self.enable_controls()
                    if not self.stop_translation:
                        messagebox.showinfo("完成", "翻译已完成！")
                    else:
                        # 如果是中止后的完成，显示不同的消息
                        status_text = self.status_label.cget("text")
                        if "已保存" in status_text:
                            messagebox.showinfo("中止完成", 
                                f"翻译已中止。\n\n{status_text}\n\n文件名包含'_partial'标识。")
                        else:
                            messagebox.showinfo("中止完成", "翻译已中止。")
                elif message["type"] == "error":
                    self.enable_controls()
                    messagebox.showerror("错误", message["text"])
                elif message["type"] == "update_models":
                    self.model_combo['values'] = message["models"]
                    if message["models"]:
                        self.model_combo.current(0)
                elif message["type"] == "preview":
                    self.preview_text.insert(tk.END, message["text"])
                    self.preview_text.see(tk.END)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.check_message_queue)

    def enable_controls(self):
        self.start_btn.config(state="normal")
        self.src_lang.config(state="readonly")
        self.dest_lang.config(state="readonly")
        self.model_combo.config(state="readonly")
        self.stop_btn.config(state="disabled")
        self.stop_translation = False
        print("控件已重新启用，中止状态已重置")

    def disable_controls(self):
        self.start_btn.config(state="disabled")
        self.src_lang.config(state="disabled")
        self.dest_lang.config(state="disabled")
        self.model_combo.config(state="disabled")
        self.stop_btn.config(state="disabled")

    def start_translation(self):
        if not hasattr(self, 'input_file'):
            messagebox.showerror("错误", "请先拖放SRT文件")
            return
        self.disable_controls()
        self.stop_btn.config(state="normal")
        self.status_label.config(text="正在翻译...")
        self.progress_bar["value"] = 0
        self.preview_text.delete(1.0, tk.END)
        self.stop_translation = False
        # 在新线程中执行翻译
        self.translation_thread = threading.Thread(target=self.translate_srt, daemon=True)
        self.translation_thread.start()

    def toggle_translate_model(self):
        """切换是否使用专用翻译模型"""
        if self.use_translate_model.get():
            # 检查专用翻译模型是否存在
            api_url = self.api_entry.get().strip()
            try:
                response = requests.get(f"{api_url}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    model_names = [model["name"] for model in models]
                    if "7shi/llama-translate:8b-q4_K_M" not in model_names:
                        # 询问用户是否要下载模型
                        if messagebox.askyesno("模型未找到", 
                            "未检测到专用翻译模型，是否现在下载？\n"
                            "下载可能需要一些时间，请确保网络连接正常。"):
                            self.message_queue.put({
                                "type": "status",
                                "text": "正在下载专用翻译模型..."
                            })
                            # 禁用控件
                            self.disable_controls()
                            # 在新线程中下载模型
                            threading.Thread(target=self.download_translate_model, daemon=True).start()
                            return
                        else:
                            # 用户取消下载，取消勾选
                            self.use_translate_model.set(False)
                            return
            except Exception as e:
                messagebox.showerror("错误", f"检查模型失败: {str(e)}")
                self.use_translate_model.set(False)
                return
                
            self.model_combo.set("7shi/llama-translate:8b-q4_K_M")
            self.model_combo.config(state="disabled")
        else:
            self.model_combo.config(state="readonly")
            self.refresh_models()

    def download_translate_model(self):
        """下载专用翻译模型"""
        try:
            api_url = self.api_entry.get().strip()
            response = requests.post(
                f"{api_url}/api/pull",
                json={"name": "7shi/llama-translate:8b-q4_K_M"}
            )
            response.raise_for_status()
            
            # 等待下载完成
            while True:
                status_response = requests.get(f"{api_url}/api/tags")
                if status_response.status_code == 200:
                    models = status_response.json().get("models", [])
                    model_names = [model["name"] for model in models]
                    if "7shi/llama-translate:8b-q4_K_M" in model_names:
                        self.message_queue.put({
                            "type": "status",
                            "text": "专用翻译模型下载完成"
                        })
                        self.message_queue.put({
                            "type": "update_models",
                            "models": model_names
                        })
                        self.enable_controls()
                        break
                time.sleep(2)  # 每2秒检查一次
                
        except Exception as e:
            self.message_queue.put({
                "type": "error",
                "text": f"下载模型失败: {str(e)}"
            })
            self.use_translate_model.set(False)
            self.enable_controls()

    def translate_with_ollama(self, text, src_lang, dest_lang, max_retries=2):
        """使用Ollama进行翻译，添加重试机制"""
        # 检查是否需要中止翻译
        if self.stop_translation:
            print("检测到中止信号，停止翻译")
            return text
        
        # 对于超长文本（超过200字符），直接返回原文
        if len(text) > 200:
            print(f"文本过长({len(text)}字符)，直接返回原文: {text[:50]}...")
            return text
        
        # 对于较短的文本，增加重试次数
        if len(text) < 50:
            max_retries = 3
        
        # 如果文本包含特殊字符或格式，可能容易卡住，降低重试次数
        if any(char in text for char in ['♪', '♫', '※', '●', '■', '★']):
            max_retries = 1
            print(f"检测到特殊字符，降低重试次数: {text[:30]}...")
        
        for attempt in range(max_retries):
            # 在每次重试前检查中止信号
            if self.stop_translation:
                print("检测到中止信号，停止重试")
                return text
                
            try:
                if self.use_translate_model.get():
                    result = self.translate_with_special_model(text, src_lang, dest_lang)
                    print(f"专用模型翻译成功: {result[:50]}...")
                    return result
                else:
                    result = self.translate_with_general_model(text, src_lang, dest_lang)
                    print(f"通用模型翻译成功: {result[:50]}...")
                    return result
            except Exception as e:
                print(f"翻译尝试 {attempt + 1} 失败: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(1)  # 减少等待时间到1秒
                    continue
                # 最后一次尝试失败，返回原文确保不丢失
                print(f"翻译多次失败，返回原文: {text[:50]}...")
                return text

    def translate_with_special_model(self, text, src_lang, dest_lang):
        """使用专用翻译模型进行翻译"""
        try:
            lang_map = {'中文': 'Mandarin', '英语': 'English', '日语': 'Japanese'}
            from_lang = lang_map[src_lang]
            to_lang = lang_map[dest_lang]
            
            prompt = f"""### Instruction:
Translate {from_lang} to {to_lang}.

### Input:
{text}

### Response:
"""
            messages = [{"role": "user", "content": prompt}]
            
            # 设置超时，使用ollama的超时参数
            response = ollama.chat(
                model="7shi/llama-translate:8b-q4_K_M", 
                messages=messages,
                options={"timeout": 2}  # 2秒超时，更快响应中止信号
            )
            result = response["message"]["content"].strip()
            
            # 检查结果是否合理
            if not result or len(result) > len(text) * 3:  # 如果翻译结果异常长，可能有问题
                print(f"专用模型翻译结果异常，原文长度: {len(text)}, 译文长度: {len(result)}")
                if not result:
                    raise Exception("翻译结果为空")
            
            return result
        except Exception as e:
            raise Exception(f"专用翻译模型调用失败: {str(e)}")

    def translate_with_general_model(self, text, src_lang, dest_lang):
        """使用通用模型进行翻译"""
        api_url = self.api_entry.get().strip()
        model = self.model_combo.get()
        
        prompt = f"请将以下{src_lang}文本翻译成{dest_lang}，只返回翻译结果，不要添加任何解释：\n{text}"
        
        try:
            response = requests.post(
                f"{api_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=2  # 2秒超时，更快响应中止信号
            )
            response.raise_for_status()
            result = response.json()
            return result["response"].strip()
        except requests.exceptions.Timeout:
            raise Exception(f"请求超时(2秒)，自动跳过: {text[:30]}...")
        except Exception as e:
            raise Exception(f"Ollama API调用失败: {str(e)}")

    def translate_srt(self):
        try:
            src_lang = self.src_lang.get()
            dest_lang = self.dest_lang.get()
            subs = self.parse_srt(self.input_file)
            total_subs = len(subs)
            print(f"开始翻译，总共 {total_subs} 条字幕")
            # 设置进度条最大值
            self.progress_bar["maximum"] = total_subs
            self.message_queue.put({"type": "progress", "value": 0})
            self.message_queue.put({"type": "status", "text": f"正在翻译... (0/{total_subs})"})
            
            translated_subs = []
            compressed_count = 0  # 统计压缩的句子数量
            
            for i, sub in enumerate(subs):
                current_progress = i + 1
                print(f"=== 处理第 {current_progress}/{total_subs} 条字幕 ===")
                print(f"原始索引: {sub.index}, 时间: {sub.start} --> {sub.end}")
                print(f"内容: {sub.content[:100]}...")
                
                # 检查是否需要中止（移到循环最开始）
                if self.stop_translation:
                    print(f"翻译被中止，已完成 {i}/{total_subs} 条字幕")
                    if translated_subs:  # 如果有已翻译的内容，保存它们
                        print(f"正在保存 {len(translated_subs)} 条已翻译的字幕...")
                        self.save_partial_translation(translated_subs, self.input_file, src_lang, dest_lang)
                        self.message_queue.put({
                            "type": "status",
                            "text": f"翻译已中止，已保存 {len(translated_subs)} 条翻译结果"
                        })
                    else:
                        self.message_queue.put({
                            "type": "status",
                            "text": "翻译已中止"
                        })
                    # 立即发送完成信号
                    self.message_queue.put({
                        "type": "complete"
                    })
                    print("中止处理完成，退出翻译线程")
                    return
                
                # 初始化默认值，确保每条都有输出
                translated_text = sub.content  # 默认使用原文
                was_compressed = False
                
                try:
                    original_start = sub.start
                    original_end = sub.end
                    original_text = sub.content
                    
                    # 第一步：检查并提取重复字符的核心内容
                    core_text, has_repetition, repetition_info = self.compress_repetitive_text(original_text)
                    if has_repetition:
                        compressed_count += 1
                        print(f"第 {current_progress} 条检测到重复字符，提取核心内容: {original_text[:30]}... → {core_text[:30]}...")
                    
                    # 第二步：决定使用哪个文本进行翻译
                    if has_repetition:
                        text_to_translate = core_text
                        print(f"第 {current_progress} 条使用提取的核心内容进行翻译: {core_text[:50]}...")
                    else:
                        text_to_translate = original_text
                        print(f"第 {current_progress} 条使用原文进行翻译: {original_text[:50]}...")
                    
                    # 第三步：翻译核心文本
                    try:
                        translated_core = self.translate_with_ollama(text_to_translate, src_lang, dest_lang)
                        if translated_core and translated_core.strip():
                            print(f"第 {current_progress} 条核心内容翻译成功: {translated_core[:50]}...")
                            
                            # 第四步：如果有重复信息，重新组合翻译结果
                            if has_repetition and repetition_info:
                                translated_text = self.reconstruct_with_repetition(translated_core, repetition_info)
                                print(f"第 {current_progress} 条重新组合后: {translated_text[:50]}...")
                            else:
                                translated_text = translated_core
                        else:
                            print(f"第 {current_progress} 条翻译结果为空，使用原文")
                            translated_text = original_text
                    except Exception as e:
                        print(f"第 {current_progress} 条翻译失败: {str(e)}，使用原文")
                        translated_text = original_text
                    
                except Exception as e:
                    print(f"第 {current_progress} 条处理过程出错: {str(e)}，使用原文")
                    translated_text = sub.content
                
                # 无论如何都要创建并添加字幕条目，确保不丢失
                new_index = len(translated_subs) + 1
                translated_sub = srt.Subtitle(
                    new_index,
                    sub.start,
                    sub.end,
                    translated_text
                )
                translated_subs.append(translated_sub)
                print(f"第 {current_progress} 条已添加到结果列表，新索引: {new_index}")
                
                # 更新进度和预览
                if compressed_count > 0:
                    status_suffix = f" (已提取重复内容 {compressed_count} 条)"
                else:
                    status_suffix = ""
                
                preview_prefix = f"[{current_progress}/{total_subs}]"
                if has_repetition:
                    preview_prefix += " [重复内容已提取]"
                
                self.message_queue.put({"type": "progress", "value": current_progress})
                self.message_queue.put({
                    "type": "status",
                    "text": f"正在翻译... ({current_progress}/{total_subs}){status_suffix}"
                })
                
                # 显示详细的处理信息
                if has_repetition and repetition_info:
                    repetition_desc = []
                    for info in repetition_info:
                        if info['type'] == 'continuous':
                            repetition_desc.append(f"连续重复'{info['char']}'×{info['count']}")
                        elif info['type'] == 'scattered':
                            repetition_desc.append(f"分散重复'{info['char']}'×{info['count']}")
                    
                    self.message_queue.put({
                        "type": "preview",
                        "text": f"{preview_prefix} 原文: {sub.content[:50]}...\n提取核心: {core_text[:50]}...\n重复信息: {', '.join(repetition_desc)}\n译文: {translated_text[:50]}...\n\n"
                    })
                else:
                    self.message_queue.put({
                        "type": "preview",
                        "text": f"{preview_prefix} 原文: {sub.content[:50]}...\n译文: {translated_text[:50]}...\n\n"
                    })
                
                print(f"第 {current_progress} 条处理完成，当前结果列表长度: {len(translated_subs)}")
            
            # 翻译完成，保存文件
            print(f"所有翻译完成，最终结果: {len(translated_subs)} 条字幕")
            if not self.stop_translation:
                print("翻译全部完成，正在保存文件...")
                self.write_srt(translated_subs, self.input_file)
                final_message = f"翻译完成！共处理 {len(translated_subs)} 条字幕"
                if compressed_count > 0:
                    final_message += f"，其中 {compressed_count} 条提取并重构了重复内容"
                self.message_queue.put({
                    "type": "status",
                    "text": final_message
                })
                self.message_queue.put({"type": "complete"})
        except Exception as e:
            print(f"翻译过程发生严重错误: {str(e)}")
            self.message_queue.put({"type": "error", "text": f"翻译失败：{str(e)}"})

    def on_drag_enter(self, event):
        self.drop_label.config(text="释放文件以导入")
        return "break"

    def on_drag_leave(self, event):
        self.drop_label.config(text="将SRT文件拖放到此处")
        return "break"

    def on_drop(self, event):
        # 获取拖放文件列表
        file_path = os.path.normpath(event.data.strip('{}').replace('{', '').replace('}', ''))
        if not os.path.exists(file_path):
            messagebox.showerror("错误", "文件路径不存在")
            return
        self.input_file = file_path
        self.drop_label.config(text=f"已选择文件：{os.path.basename(file_path)}")

    def parse_srt(self, file_path):
        try:
            # 尝试导入charset_normalizer进行编码检测
            import charset_normalizer
            with open(file_path, 'rb') as f:
                raw = f.read()
                result = charset_normalizer.from_bytes(raw)
                encoding = result.best().encoding if result.best() else 'utf-8'
                print(f"检测到文件编码: {encoding}")
                content = raw.decode(encoding, errors='replace')
        except ImportError:
            print("未安装charset-normalizer，使用备用编码检测方法")
            # 如果没有charset_normalizer，使用多种编码尝试
            encodings = ['utf-8', 'gbk', 'shift-jis', 'cp932', 'iso-8859-1']
            content = None
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    print(f"使用编码 {encoding} 成功读取文件")
                    break
                except UnicodeDecodeError:
                    print(f"编码 {encoding} 读取失败，尝试下一个...")
                    continue
            
            if content is None:
                print("所有编码尝试失败，使用UTF-8容错模式")
                # 如果所有编码都失败，使用utf-8并忽略错误
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
        
        return list(parse(content))

    def save_partial_translation(self, translated_subs, input_path, src_lang, dest_lang):
        """保存部分翻译结果"""
        try:
            lang_map = {'中文': 'zh', '英语': 'en', '日语': 'ja'}
            from_code = lang_map[src_lang]
            to_code = lang_map[dest_lang]
            file_name, file_ext = os.path.splitext(input_path)
            
            # 从名称尾部查找原语言映射词并删除
            if file_name.endswith(from_code):
                file_name = file_name[:-(len(from_code))]
            
            # 加上目标语言映射词和部分标识
            output_path = file_name + to_code + "_partial" + file_ext
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(compose(translated_subs))
            
            print(f"部分翻译结果已保存到: {output_path}")
            return output_path
        except Exception as e:
            print(f"保存部分翻译结果失败: {str(e)}")
            return None

    def write_srt(self, translated_subs, input_path):
        src_lang = self.src_lang.get()
        dest_lang = self.dest_lang.get()
        lang_map = {'中文': 'zh', '英语': 'en', '日语': 'ja'}
        from_code = lang_map[src_lang]
        to_code = lang_map[dest_lang]
        file_name, file_ext = os.path.splitext(input_path)
        # 从名称尾部查找原语言映射词并删除
        if file_name.endswith(from_code):
            file_name = file_name[:-(len(from_code))]
        # 加上目标语言映射词
        output_path = file_name + to_code + file_ext
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(compose(translated_subs))

    def update_dest_lang(self, event=None):
        src_lang = self.src_lang.get()
        lang_map = {
            "英语": ["中文", "日语"],
            "日语": ["中文", "英语"],
            "中文": ["英语", "日语"]
        }
        self.dest_lang['values'] = lang_map.get(src_lang, ["中文"])
        self.dest_lang.current(0)

    def stop_translation_process(self):
        """中止翻译过程"""
        if self.translation_thread and self.translation_thread.is_alive():
            # 确认用户是否要中止
            result = messagebox.askyesno("确认中止", 
                "确定要中止翻译吗？\n\n已翻译的部分将保存为临时文件（文件名包含_partial）")
            if result:
                print("用户确认中止翻译")
                self.stop_translation = True
                self.message_queue.put({
                    "type": "status",
                    "text": "正在中止翻译，请稍候..."
                })
                self.stop_btn.config(state="disabled")
                
                # 设置超时，如果线程5秒内没有结束，强制标记为完成
                def force_complete():
                    time.sleep(5)  # 等待5秒
                    if self.translation_thread and self.translation_thread.is_alive():
                        print("翻译线程超时，强制完成")
                        self.message_queue.put({
                            "type": "status",
                            "text": "翻译已强制中止"
                        })
                        self.message_queue.put({
                            "type": "complete"
                        })
                
                # 启动超时处理线程
                threading.Thread(target=force_complete, daemon=True).start()
            # 如果用户选择不中止，什么都不做

    def compress_repetitive_text(self, text):
        """检测重复字符并提取核心内容用于翻译，返回核心内容和重复信息"""
        if len(text.strip()) < 5:
            return text, False, None
        
        original_text = text
        repetition_info = []  # 存储重复信息
        
        # 第一步：检测短语重复（如：いいよ、いいよ、いいよ、 → いいよ*N）
        # 检测常见的短语重复模式
        phrase_patterns = [
            r'(いいよ[、。，！？\s]*){4,}',  # いいよ重复
            r'(そう[、。，！？\s]*){4,}',   # そう重复
            r'(はい[、。，！？\s]*){4,}',   # はい重复
            r'(ああ[、。，！？\s]*){4,}',   # ああ重复
            r'(うん[、。，！？\s]*){4,}',   # うん重复
            r'([^、。，！？\s]{1,3}[、。，！？\s]*)\1{3,}',  # 通用短语重复检测
        ]
        
        for pattern in phrase_patterns:
            matches = list(re.finditer(pattern, text))
            if matches:
                for match in matches:
                    full_match = match.group(0)
                    repeated_phrase = match.group(1) if match.groups() else match.group(0)
                    
                    # 计算重复次数
                    count = len(re.findall(re.escape(repeated_phrase.rstrip('、。，！？ \n')), full_match))
                    
                    if count >= 4:  # 至少重复4次
                        repetition_info.append({
                            'type': 'phrase',
                            'phrase': repeated_phrase.rstrip('、。，！？ \n'),
                            'count': count,
                            'start': match.start(),
                            'end': match.end()
                        })
                        
                        # 替换为单个短语
                        core_text = text[:match.start()] + repeated_phrase.rstrip('、。，！？ \n') + text[match.end():]
                        print(f"检测到短语重复'{repeated_phrase.rstrip('、。，！？ \n')}'×{count}，核心内容: {core_text[:50]}...")
                        return core_text, True, repetition_info
        
        # 第二步：检测连续重复的单字符（如：ああああ → あ*4）
        pattern = r'(.)\1{3,}'  # 匹配连续重复4次及以上的字符
        matches = list(re.finditer(pattern, text))
        
        if matches:
            # 找到连续重复，提取重复信息
            for match in matches:
                char = match.group(1)
                count = len(match.group(0))
                repetition_info.append({
                    'type': 'continuous',
                    'char': char,
                    'count': count,
                    'start': match.start(),
                    'end': match.end()
                })
            
            # 移除重复部分，保留核心内容
            core_text = text
            for match in reversed(matches):  # 从后往前替换，避免位置偏移
                core_text = core_text[:match.start()] + match.group(1) + core_text[match.end():]
            
            print(f"检测到连续重复，核心内容: {core_text[:50]}...")
            return core_text, True, repetition_info
        
        # 第三步：检测分散的重复字符（如：お、お、お、お → お*8）
        import collections
        char_count = collections.Counter(re.sub(r'[、。，！？\s]', '', text))
        
        for char, count in char_count.items():
            if count >= 8:  # 如果某个字符出现8次以上
                # 找到包含该字符的所有位置
                pattern = f"{re.escape(char)}[、。，！？\\s]*"
                matches = list(re.finditer(pattern, text))
                
                if len(matches) >= 6:
                    # 记录重复信息
                    repetition_info.append({
                        'type': 'scattered',
                        'char': char,
                        'count': len(matches),
                        'positions': [m.span() for m in matches]
                    })
                    
                    # 移除重复的字符，只保留一个和其他内容
                    core_text = text
                    # 简单处理：移除多余的重复字符
                    core_text = re.sub(f"({re.escape(char)}[、。，！？\\s]*)+", char, core_text)
                    
                    print(f"检测到分散重复字符'{char}': 出现{len(matches)}次，核心内容: {core_text[:50]}...")
                    return core_text, True, repetition_info
        
        return text, False, None

    def reconstruct_with_repetition(self, translated_text, repetition_info):
        """将翻译后的文本与重复信息重新组合"""
        if not repetition_info:
            return translated_text
        
        result = translated_text
        
        for info in repetition_info:
            if info['type'] == 'phrase':
                # 短语重复：翻译短语后加上重复次数
                original_phrase = info['phrase']
                count = info['count']
                
                # 常见短语的翻译映射
                phrase_translation = {
                    'いいよ': '好的',
                    'そう': '对',
                    'はい': '是的',
                    'ああ': '啊',
                    'うん': '嗯'
                }
                
                # 尝试翻译短语
                if original_phrase in phrase_translation:
                    translated_phrase = phrase_translation[original_phrase]
                else:
                    # 如果翻译结果中包含原短语，保持原样
                    translated_phrase = original_phrase
                
                # 在翻译结果前加上重复标记
                if original_phrase in result:
                    result = result.replace(original_phrase, f"{translated_phrase}*{count}", 1)
                else:
                    result = f"{translated_phrase}*{count}" + result
                
                print(f"重构短语重复: {original_phrase}*{count} → {translated_phrase}*{count}")
                
            elif info['type'] == 'continuous':
                # 连续重复：在翻译结果前加上重复标记
                original_char = info['char']
                count = info['count']
                # 尝试找到原字符对应的翻译字符
                # 简单处理：如果翻译结果包含对应字符，则添加重复标记
                if original_char in ['あ', 'お']:
                    if 'あ' in translated_text or '啊' in translated_text:
                        result = f"啊*{count}" + result.replace('啊', '')
                    elif 'お' in translated_text or '哦' in translated_text:
                        result = f"哦*{count}" + result.replace('哦', '')
                    else:
                        # 如果没有找到对应字符，在开头添加
                        translated_char = '啊' if original_char == 'あ' else '哦' if original_char == 'お' else original_char
                        result = f"{translated_char}*{count}" + result
                
            elif info['type'] == 'scattered':
                # 分散重复：类似处理
                original_char = info['char']
                count = info['count']
                if original_char in ['あ', 'お']:
                    translated_char = '啊' if original_char == 'あ' else '哦' if original_char == 'お' else original_char
                    result = f"{translated_char}*{count}" + result.replace(translated_char, '', 1)
        
        return result

    def has_excessive_repetition(self, text):
        """检测文本是否包含大量重复字符，这类文本容易让LLM卡住"""
        # 去除标点符号，只检查核心内容
        clean_text = re.sub(r'[、。，！？\s]', '', text)
        
        if len(clean_text) < 5:  # 太短的文本不检测
            return False
        
        # 检测1：单字符重复超过10次
        for char in set(clean_text):
            if clean_text.count(char) > 10:
                print(f"发现字符'{char}'重复{clean_text.count(char)}次")
                return True
        
        # 检测2：相同的2-3字符片段重复超过5次
        for length in [2, 3]:
            for i in range(len(clean_text) - length + 1):
                fragment = clean_text[i:i+length]
                count = len(re.findall(re.escape(fragment), clean_text))
                if count > 5:
                    print(f"发现片段'{fragment}'重复{count}次")
                    return True
        
        # 检测3：字符种类太少（可能全是重复）
        unique_chars = len(set(clean_text))
        if len(clean_text) > 50 and unique_chars < 5:
            print(f"文本长度{len(clean_text)}但只有{unique_chars}种字符")
            return True
        
        return False

if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = SRTTranslatorApp(root)
    root.mainloop() 