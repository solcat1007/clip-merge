"""
片段合并器 v1.0 — 纯 tkinter GUI 工具
功能：将多个视频文件按指定顺序无损合并为一个文件（使用 ffmpeg concat demuxer）
依赖：Python 标准库 + ffmpeg（需自行安装并加入 PATH）
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import threading
import os
import tempfile

# ============================================================
# 全局常量
# ============================================================
WIN_WIDTH = 500          # 窗口宽度
WIN_HEIGHT = 350         # 窗口高度
BG_COLOR = "#1e1e2e"     # 深色背景
ACCENT_COLOR = "#4ade80" # 强调色（绿色）
FG_COLOR = "#cdd6f4"     # 浅色前景文字
BTN_BG = "#313244"       # 按钮背景
ENTRY_BG = "#313244"     # 输入框背景
LISTBOX_BG = "#181825"   # 列表背景
VIDEO_EXTS = (".mp4", ".mkv", ".avi", ".mov")  # 支持的视频格式


def check_ffmpeg():
    """检查 ffmpeg 是否可用"""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


class ClipMergeApp:
    """片段合并器主应用"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("片段合并器 v1.0")
        self.root.geometry(f"{WIN_WIDTH}x{WIN_HEIGHT}")
        self.root.resizable(False, False)  # 禁止调整窗口大小
        self.root.configure(bg=BG_COLOR)

        # 存储已添加的视频文件路径（与 Listbox 索引对齐）
        self.file_list: list[str] = []

        self._build_ui()

    # ----------------------------------------------------------
    # UI 构建
    # ----------------------------------------------------------
    def _build_ui(self):
        """构建全部界面组件"""
        # --- 顶栏：添加文件按钮 ---
        top_frame = tk.Frame(self.root, bg=BG_COLOR)
        top_frame.pack(pady=(12, 6), padx=12, fill=tk.X)

        self.btn_add = tk.Button(
            top_frame,
            text="＋ 添加文件",
            command=self._add_files,
            bg=ACCENT_COLOR,
            fg=BG_COLOR,
            activebackground="#34d399",
            activeforeground=BG_COLOR,
            font=("Microsoft YaHei UI", 10, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            padx=16,
            pady=4,
        )
        self.btn_add.pack(fill=tk.X)

        # --- 文件列表 + 排序按钮 ---
        list_frame = tk.Frame(self.root, bg=BG_COLOR)
        list_frame.pack(pady=(0, 6), padx=12, fill=tk.BOTH, expand=True)

        # Listbox 用于展示已添加文件
        self.listbox = tk.Listbox(
            list_frame,
            bg=LISTBOX_BG,
            fg=FG_COLOR,
            selectbackground=ACCENT_COLOR,
            selectforeground=BG_COLOR,
            font=("Consolas", 10),
            activestyle="none",
            relief=tk.FLAT,
            highlightthickness=0,
        )
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 垂直滚动条
        scrollbar = tk.Scrollbar(list_frame, bg=BG_COLOR, troughcolor=BG_COLOR)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.listbox.yview)

        # --- 排序 / 删除按钮行 ---
        sort_frame = tk.Frame(self.root, bg=BG_COLOR)
        sort_frame.pack(pady=(0, 8), padx=12, fill=tk.X)

        self.btn_up = tk.Button(
            sort_frame,
            text="▲ 上移",
            command=self._move_up,
            bg=BTN_BG,
            fg=FG_COLOR,
            activebackground="#45475a",
            activeforeground=FG_COLOR,
            font=("Microsoft YaHei UI", 9),
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=2,
        )
        self.btn_up.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_down = tk.Button(
            sort_frame,
            text="▼ 下移",
            command=self._move_down,
            bg=BTN_BG,
            fg=FG_COLOR,
            activebackground="#45475a",
            activeforeground=FG_COLOR,
            font=("Microsoft YaHei UI", 9),
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=2,
        )
        self.btn_down.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_remove = tk.Button(
            sort_frame,
            text="✕ 删除",
            command=self._remove_selected,
            bg="#ef4444",
            fg="#ffffff",
            activebackground="#dc2626",
            activeforeground="#ffffff",
            font=("Microsoft YaHei UI", 9),
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=2,
        )
        self.btn_remove.pack(side=tk.LEFT)

        # --- 输出文件名输入框 ---
        out_frame = tk.Frame(self.root, bg=BG_COLOR)
        out_frame.pack(pady=(0, 8), padx=12, fill=tk.X)

        out_label = tk.Label(
            out_frame,
            text="输出文件名：",
            bg=BG_COLOR,
            fg=FG_COLOR,
            font=("Microsoft YaHei UI", 9),
        )
        out_label.pack(side=tk.LEFT)

        self.out_name_var = tk.StringVar(value="merged_output")
        self.out_entry = tk.Entry(
            out_frame,
            textvariable=self.out_name_var,
            bg=ENTRY_BG,
            fg=FG_COLOR,
            insertbackground=FG_COLOR,
            relief=tk.FLAT,
            font=("Consolas", 10),
        )
        self.out_entry.pack(side=tk.LEFT, padx=(8, 0), fill=tk.X, expand=True)

        # --- 无损合并按钮 ---
        self.btn_merge = tk.Button(
            self.root,
            text="无损合并",
            command=self._start_merge,
            bg=ACCENT_COLOR,
            fg=BG_COLOR,
            activebackground="#34d399",
            activeforeground=BG_COLOR,
            font=("Microsoft YaHei UI", 12, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            padx=20,
            pady=6,
        )
        self.btn_merge.pack(pady=(0, 4), padx=12, fill=tk.X)

        # --- 状态栏 ---
        self.status_var = tk.StringVar(value="就绪")
        self.status_bar = tk.Label(
            self.root,
            textvariable=self.status_var,
            bg=BG_COLOR,
            fg="#6c7086",
            font=("Microsoft YaHei UI", 9),
            anchor=tk.W,
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(0, 8))

    # ----------------------------------------------------------
    # 功能方法
    # ----------------------------------------------------------
    def _set_status(self, text: str):
        """更新状态栏文本"""
        self.status_var.set(text)

    def _add_files(self):
        """打开文件选择对话框，添加视频文件到列表"""
        paths = filedialog.askopenfilenames(
            title="选择视频文件",
            filetypes=[
                ("视频文件", "*.mp4 *.mkv *.avi *.mov"),
                ("所有文件", "*.*"),
            ],
        )
        for path in paths:
            # 去重：避免重复添加同一文件
            if path not in self.file_list:
                self.file_list.append(path)
                # Listbox 只显示文件名
                self.listbox.insert(tk.END, os.path.basename(path))
        self._set_status(f"已添加 {len(paths)} 个文件，共 {len(self.file_list)} 个")

    def _move_up(self):
        """将选中项上移一位"""
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx == 0:
            return  # 已在顶部
        # 交换 Listbox 显示
        self.listbox.insert(idx - 1, self.listbox.get(idx))
        self.listbox.delete(idx + 1)
        self.listbox.selection_set(idx - 1)
        # 交换底层数据
        self.file_list[idx], self.file_list[idx - 1] = (
            self.file_list[idx - 1],
            self.file_list[idx],
        )

    def _move_down(self):
        """将选中项下移一位"""
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(self.file_list) - 1:
            return  # 已在底部
        # 交换 Listbox 显示
        self.listbox.insert(idx + 2, self.listbox.get(idx))
        self.listbox.delete(idx)
        self.listbox.selection_set(idx + 1)
        # 交换底层数据
        self.file_list[idx], self.file_list[idx + 1] = (
            self.file_list[idx + 1],
            self.file_list[idx],
        )

    def _remove_selected(self):
        """删除选中项"""
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self.listbox.delete(idx)
        del self.file_list[idx]
        self._set_status(f"已删除，剩余 {len(self.file_list)} 个文件")

    def _start_merge(self):
        """启动合并线程（避免阻塞 UI）"""
        if not self.file_list:
            messagebox.showwarning("提示", "请先添加视频文件")
            return
        self.btn_merge.config(state=tk.DISABLED)
        self._set_status("合并中...")
        thread = threading.Thread(target=self._merge, daemon=True)
        thread.start()

    def _merge(self):
        """在后台线程中执行 ffmpeg 无损合并"""
        try:
            # 1. 检查 ffmpeg
            if not check_ffmpeg():
                self._ui_message(
                    "错误", "请安装 ffmpeg 并添加到 PATH 环境变量", is_error=True
                )
                return

            # 2. 生成临时 concat 文件列表（ffmpeg concat demuxer 格式）
            # 格式: file '完整路径'
            # 路径中的单引号需转义为 \'
            concat_content = ""
            for path in self.file_list:
                escaped = path.replace("'", "'\\''")
                concat_content += f"file '{escaped}'\n"

            # 输出路径：与第一个输入文件同目录
            out_dir = os.path.dirname(self.file_list[0])
            out_name = self.out_name_var.get().strip()
            if not out_name:
                out_name = "merged_output"
            if not out_name.lower().endswith(".mp4"):
                out_name += ".mp4"
            out_path = os.path.join(out_dir, out_name)

            # 写入临时文件列表
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".txt", prefix="ffconcat_")
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                    f.write(concat_content)

                # 3. 调用 ffmpeg 无损合并
                cmd = [
                    "ffmpeg",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", tmp_path,
                    "-c", "copy",
                    "-y",
                    out_path,
                ]
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                )
                if proc.returncode != 0:
                    self._ui_message(
                        "合并失败",
                        f"ffmpeg 返回非零退出码：\n{proc.stderr[-500:]}",
                        is_error=True,
                    )
                    return

            finally:
                # 清理临时文件
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

            # 4. 完成
            self._ui_message("完成", f"无损合并完成！\n输出文件：{out_path}")
            self._set_status("完成！")
        except Exception as e:
            self._ui_message("异常", f"合并过程中发生异常：\n{str(e)}", is_error=True)
        finally:
            # 恢复按钮状态（需要在主线程操作）
            self.root.after(0, lambda: self.btn_merge.config(state=tk.NORMAL))

    def _ui_message(self, title: str, msg: str, is_error: bool = False):
        """
        安全在主线程中弹出消息框。
        因为合并操作在后台线程，tkinter 消息框必须在主线程调用。
        """
        fn = messagebox.showerror if is_error else messagebox.showinfo
        self.root.after(0, lambda: fn(title, msg))


# ============================================================
# 入口
# ============================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = ClipMergeApp(root)
    root.mainloop()
