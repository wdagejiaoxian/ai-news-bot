"""
内容转换器模块

负责将过长的Markdown内容转换为：
1. PDF文件（用于文件发送）
2. Markdown文件（用于文件发送）
3. 卡片消息（用于降级处理）
"""

import io
import os
from datetime import datetime
from typing import Tuple

from app.config import get_settings

# 长度阈值（保留200字节余量）
MAX_CONTENT_LENGTH = 3800  # 字节


class ContentConverter:
    """内容转换器"""

    def __init__(self):
        self.settings = get_settings()
        self.storage_path = self.settings.report_storage_path

    def check_length(self, content: str) -> bool:
        """检查内容是否超过长度限制"""
        return len(content.encode('utf-8')) > MAX_CONTENT_LENGTH

    def generate_filename(self, prefix: str = "report") -> str:
        """生成文件名"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{timestamp}.md"

    def generate_pdf_filename(self, prefix: str = "report") -> str:
        """生成pdf文件名"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{timestamp}.pdf"

    # ========== PDF转换 ==========
    async def markdown_to_pdf(self, markdown_content: str) -> bytes:
        """
        将Markdown内容转换为PDF

        Args:
            markdown_content: Markdown格式内容

        Returns:
            bytes: PDF文件字节流
        """
        import io
        from weasyprint import HTML
        import mistune

        md = mistune.create_markdown(
            # hard_wrap=True,
            plugins=[
                'table',
                'task_lists',  # 任务列表
                'strikethrough',  # 删除线
                'math',
                'url',  # 自动链接
                'abbr',  # 缩写
                'mark',  # 高亮 ==text==
                'footnotes',  # 脚注
            ]
        )
        html_body = md(markdown_content)

        # 简单的HTML模板
        # 2. 构建完整的HTML文档（带样式）
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <style>
        /* ===== 深色主题配色方案 ===== */
        :root {{
            --bg-primary: #1a1b26;        /* 主背景：深蓝灰，比纯黑柔和 */
            --bg-secondary: #24283b;       /* 次级背景：卡片、代码块 */
            --bg-tertiary: #2a2f45;        /* 第三层背景：表格、引用 */
            --text-primary: #c0caf5;       /* 主文字：淡紫蓝白，柔和不刺眼 */
            --text-secondary: #a9b1d6;     /* 次要文字：中灰紫 */
            --text-muted: #565f89;         /* 辅助文字：暗灰 */
            --accent-primary: #7aa2f7;     /* 强调色：天蓝 */
            --accent-secondary: #bb9af7;   /* 次要强调：粉紫 */
            --accent-success: #9ece6a;     /* 成功/任务完成：嫩绿 */
            --border-color: #414868;       /* 边框色 */
            --code-bg: #16161e;            /* 代码背景：更深 */
        }}
        
        @page {{ 
            size: A4; 
            margin: 1.8cm;
            background: var(--bg-primary);
            @bottom-center {{
                content: "第 " counter(page) " 页";
                font-size: 11pt;
                color: var(--text-muted);
                font-family: "Noto Sans CJK SC", "Noto Color Emoji", sans-serif;
            }}
        }}
        
        * {{
            box-sizing: border-box;
            -webkit-font-smoothing: antialiased;
        }}
        
        /* ===== 基础大字体设置 ===== */
        body {{
            font-family: "Noto Sans CJK SC", "Noto Color Emoji", "WenQuanYi Micro Hei", sans-serif;
            font-size: 16pt;               /* 手机舒适阅读大小 */
            line-height: 1.85;             /* 更大行距，阅读舒适 */
            color: var(--text-primary);
            background: var(--bg-primary);
            margin: 0;
            padding: 0;
            letter-spacing: 0.3px;         /* 微字间距，深色下更清晰 */
        }}
        
        /* ===== 大标题层级 ===== */
        h1 {{
            font-size: 28pt;               /* 超大标题 */
            font-weight: 700;
            color: #ffffff;
            margin: 0 0 24pt 0;
            padding-bottom: 16pt;
            border-bottom: 3px solid var(--accent-primary);
            text-shadow: 0 2px 4px rgba(122, 162, 247, 0.2);
            letter-spacing: -0.5px;
        }}
        
        h2 {{
            font-size: 22pt;               /* 大二级标题 */
            font-weight: 600;
            color: var(--accent-primary);
            margin: 28pt 0 14pt 0;
            padding: 12pt 0 12pt 20pt;
            background: linear-gradient(90deg, var(--bg-secondary) 0%, transparent 100%);
            border-left: 5px solid var(--accent-primary);
            border-radius: 0 8px 8px 0;
        }}
        
        h3 {{
            font-size: 18pt;               /* 大三级标题 */
            font-weight: 600;
            color: var(--accent-secondary);
            margin: 22pt 0 12pt 0;
            padding: 10pt 0 10pt 20pt;
            background: linear-gradient(90deg, rgba(187, 154, 247, 0.1) 0%, transparent 100%);
            border-left: 4px solid var(--accent-secondary);
            border-radius: 0 8px 8px 0;
            line-height: 1.4;
        }}
        h3 a {{
            color: var(--accent-primary);  /* 用蓝色区分链接 */
            text-decoration: none;         /* 确保没有双重下划线 */
            border-bottom: 1px solid currentColor;  /* 细下划线，不增加高度 */
            padding-bottom: 0;             /* 去掉 padding-bottom，避免撑高行距 */
            text-shadow: none;             /* 去掉发光效果，避免视觉混乱 */
            font-weight: 600;              /* 保持与 h3 一致的粗细 */
        }}
        
        /* 可选：鼠标悬停效果 */
        h3 a:hover {{
            color: #ffffff;
            border-bottom-color: #ffffff;
        }}
        
        /* ===== 链接 - 发光效果 ===== */
        a {{
            color: var(--accent-primary);
            text-decoration: none;
            border-bottom: 2px solid rgba(122, 162, 247, 0.3);
            padding-bottom: 1px;
            font-weight: 500;
            transition: all 0.2s;
        }}
        
        a:hover {{
            color: #ffffff;
            border-bottom-color: var(--accent-primary);
            text-shadow: 0 0 8px rgba(122, 162, 247, 0.5);
        }}
        
        /* ===== 段落与文本 ===== */
        p {{
            margin: 0 0 16pt 0;
            text-align: justify;
            color: var(--text-primary);
        }}
        
        strong {{
            color: #ffffff;
            font-weight: 600;
            background: rgba(122, 162, 247, 0.15);
            padding: 2px 6px;
            border-radius: 4px;
        }}
        
        em {{
            color: var(--accent-secondary);
            font-style: italic;
        }}
        
        /* 高亮标记 - 深色下的荧光效果 */
        mark {{
            background: rgba(187, 154, 247, 0.25);
            color: #e0def4;
            padding: 3px 8px;
            border-radius: 4px;
            font-weight: 600;
            border: 1px solid rgba(187, 154, 247, 0.4);
        }}
        
        /* 删除线 */
        del {{
            color: var(--text-muted);
            text-decoration: line-through;
            text-decoration-color: #f7768e;
            text-decoration-thickness: 2px;
        }}
        
        
        
        /* ===== 列表 - 大间距适配手机 ===== */
        ul, ol {{
            margin: 16pt 0;
            padding-left: 32pt;            /* 更大缩进 */
        }}
        
        li {{
            margin: 10pt 0;                /* 列表项间距加大 */
            color: var(--text-primary);
            line-height: 1.9;
        }}
        
        li::marker {{
            color: var(--accent-primary);
            font-size: 1.2em;
        }}
        
        /* 任务列表 - 大复选框 */
        li.task-list-item {{
            list-style: none;
            padding-left: 8pt;
        }}
        
        li.task-list-item input[type="checkbox"] {{
            width: 16pt;
            height: 16pt;
            margin-right: 10pt;
            accent-color: var(--accent-success);
            cursor: pointer;
        }}
        
        /* ===== 代码块 - 深色专业主题 ===== */
        code {{
            font-family: "JetBrains Mono", "Fira Code", "Courier New", Consolas, monospace;
            font-size: 13pt;               /* 代码字体加大 */
            background: var(--code-bg);
            color: #ff9e64;                /* 暖橙色代码文字 */
            padding: 3px 8px;
            border-radius: 6px;
            border: 1px solid var(--border-color);
        }}
        
        pre {{
            background: var(--code-bg);
            padding: 20pt;
            border-radius: 10px;
            overflow-x: auto;
            margin: 20pt 0;
            line-height: 1.7;
            border: 1px solid var(--border-color);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
        }}
        
        pre code {{
            background: none;
            color: #c0caf5;
            padding: 0;
            border: none;
            font-size: 12.5pt;
        }}
        
        /* ===== 引用块 - 深色模式下柔和突出 ===== */
        blockquote {{
            margin: 20pt 0;
            padding: 20pt 24pt;
            background: var(--bg-tertiary);
            border-left: 5px solid var(--accent-secondary);
            border-radius: 0 12px 12px 0;
            color: var(--text-secondary);
            font-style: italic;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
        }}
        
        blockquote p {{
            margin: 0 0 8pt 0;
            color: var(--text-secondary);
            font-size: 15pt;
        }}
        
        blockquote p:last-child {{
            margin-bottom: 0;
        }}
        
        blockquote cite {{
            display: block;
            margin-top: 12pt;
            font-size: 13pt;
            color: var(--text-muted);
            font-style: normal;
            text-align: right;
        }}
        
        /* ===== 表格 - 深色主题优化 ===== */
        table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            margin: 20pt 0;
            font-size: 14pt;               /* 表格文字加大 */
            background: var(--bg-secondary);
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }}
        
        thead {{
            background: linear-gradient(135deg, #2f3549 0%, #24283b 100%);
            color: var(--accent-primary);
        }}
        
        th {{
            font-weight: 600;
            padding: 14pt 16pt;
            text-align: left;
            font-size: 13pt;
            border-bottom: 2px solid var(--accent-primary);
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        td {{
            padding: 12pt 16pt;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-primary);
            line-height: 1.7;
        }}
        
        tbody tr:nth-child(even) {{
            background: rgba(26, 27, 38, 0.4);
        }}
        
        tbody tr:hover {{
            background: rgba(122, 162, 247, 0.08);
        }}
        
        tbody tr:last-child td {{
            border-bottom: none;
        }}
        
        /* ===== 分隔线 ===== */
        hr {{
            border: none;
            height: 2px;
            background: linear-gradient(90deg, 
                transparent 0%, 
                var(--border-color) 20%, 
                var(--accent-primary) 50%, 
                var(--border-color) 80%, 
                transparent 100%
            );
            margin: 28pt 0;
            opacity: 0.6;
        }}
        
        /* ===== 脚注 ===== */
        .footnote {{
            font-size: 12pt;
            color: var(--accent-secondary);
            vertical-align: super;
            text-decoration: none;
        }}
        
        .footnotes {{
            margin-top: 36pt;
            padding-top: 20pt;
            border-top: 2px solid var(--border-color);
            font-size: 13pt;
            color: var(--text-secondary);
        }}
        
        .footnotes ol {{
            padding-left: 24pt;
        }}
        
        .footnotes li {{
            margin: 8pt 0;
            line-height: 1.6;
        }}
        
        /* ===== 上标下标 ===== */
        sup, sub {{
            font-size: 11pt;
            color: var(--accent-secondary);
        }}
        
        /* ===== 缩写 ===== */
        abbr {{
            border-bottom: 1px dashed var(--accent-primary);
            cursor: help;
            color: var(--accent-primary);
        }}
        
        /* ===== 打印优化（深色模式必须）===== */
        @media print {{
            body {{
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}
            
            /* 确保深色背景打印出来 */
            * {{
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
            }}
        }}
    </style>
</head>
<body>
{html_body}
</body>
</html>"""

        pdf_buffer = io.BytesIO()
        HTML(string=html_content).write_pdf(pdf_buffer)

        return pdf_buffer.getvalue()

    # ========== Markdown文件保存 ==========
    def save_to_markdown(self, markdown_content: str, filename: str = None) -> Tuple[str, str]:
        """保存Markdown内容到文件"""
        filename = filename or self.generate_filename()
        filepath = os.path.join(self.storage_path, filename)

        os.makedirs(self.storage_path, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        return filepath, filename

    async def markdown_to_pdf_file(self, markdown_content: str, filename: str = None) -> Tuple[str, str]:
        """
        将Markdown转换为PDF并保存到文件

        Returns:
            tuple: (文件路径, 文件名)
        """
        # 生成PDF文件
        pdf_bytes = await self.markdown_to_pdf(markdown_content)

        # 保存文件
        file_name = filename or self.generate_pdf_filename(filename)
        filepath = os.path.join(self.storage_path, file_name)

        os.makedirs(self.storage_path, exist_ok=True)

        with open(filepath, 'wb') as f:
            f.write(pdf_bytes)

        return filepath, file_name

# 创建全局转换器实例
content_converter = ContentConverter()