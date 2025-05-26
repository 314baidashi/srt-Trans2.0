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
                        messagebox.showinfo("完成", "翻译已完成")
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

    def translate_with_ollama(self, text, src_lang, dest_lang):
        """使用Ollama进行翻译"""
        if self.use_translate_model.get():
            return self.translate_with_special_model(text, src_lang, dest_lang)
        else:
            return self.translate_with_general_model(text, src_lang, dest_lang)

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
            response = ollama.chat(model="7shi/llama-translate:8b-q4_K_M", messages=messages)
            return response["message"]["content"].strip()
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
                }
            )
            response.raise_for_status()
            result = response.json()
            return result["response"].strip()
        except Exception as e:
            raise Exception(f"Ollama API调用失败: {str(e)}")

    def translate_srt(self):
        try:
            src_lang = self.src_lang.get()
            dest_lang = self.dest_lang.get()
            subs = self.parse_srt(self.input_file)
            self.message_queue.put({"type": "progress", "value": 0})
            self.message_queue.put({"type": "status", "text": "正在翻译..."})
            
            translated_subs = []
            for i, sub in enumerate(subs):
                if self.stop_translation:
                    self.message_queue.put({
                        "type": "status",
                        "text": "翻译已中止"
                    })
                    self.message_queue.put({
                        "type": "complete"
                    })
                    return
                    
                original_start = sub.start
                original_end = sub.end
                translated_text = self.translate_with_ollama(sub.content, src_lang, dest_lang)
                new_index = sub.index if len(translated_subs) == 0 else len(translated_subs) + 1
                translated_sub = srt.Subtitle(
                    new_index,
                    original_start,
                    original_end,
                    translated_text
                )
                translated_subs.append(translated_sub)
                self.message_queue.put({"type": "progress", "value": i + 1})
                self.message_queue.put({
                    "type": "preview",
                    "text": f"原文: {sub.content}\n译文: {translated_text}\n\n"
                })
            
            if not self.stop_translation:
                self.write_srt(translated_subs, self.input_file)
                self.message_queue.put({"type": "complete"})
        except Exception as e:
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
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return list(parse(content))

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
            self.stop_translation = True
            self.message_queue.put({
                "type": "status",
                "text": "正在中止翻译..."
            })
            self.stop_btn.config(state="disabled")

if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = SRTTranslatorApp(root)
    root.mainloop() 