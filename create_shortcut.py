# -*- coding: utf-8 -*-
"""
创建 RecruitFlow 桌面快捷方式
"""
import os
import sys

# 设置输出编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    from win32com.client import Dispatch
    
    # 获取桌面路径（不依赖 winshell）
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.exists(desktop):
        # 尝试使用公共桌面
        desktop = os.path.join(os.environ.get("PUBLIC", ""), "Desktop")
    
    shortcut_path = os.path.join(desktop, "RecruitFlow 启动.lnk")
    
    # 获取当前脚本所在目录的绝对路径
    current_dir = os.path.abspath(".")
    vbs_path = os.path.join(current_dir, "start_recruitflow.vbs")
    
    shell = Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.Targetpath = vbs_path
    shortcut.WorkingDirectory = current_dir
    shortcut.IconLocation = "C:\\Windows\\System32\\shell32.dll, 44"
    shortcut.save()
    
    print(f"✓ 桌面快捷方式已创建：{shortcut_path}")
    print(f"  目标：{vbs_path}")
    
except ImportError as e:
    print("缺少必要的库，请先安装：")
    print("  pip install pywin32")
    print(f"错误：{e}")
    sys.exit(1)
except Exception as e:
    print(f"创建快捷方式失败：{e}")
    sys.exit(1)


创建 RecruitFlow 桌面快捷方式
"""
import os
import sys

# 设置输出编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    from win32com.client import Dispatch
    
    # 获取桌面路径（不依赖 winshell）
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.exists(desktop):
        # 尝试使用公共桌面
        desktop = os.path.join(os.environ.get("PUBLIC", ""), "Desktop")
    
    shortcut_path = os.path.join(desktop, "RecruitFlow 启动.lnk")
    
    # 获取当前脚本所在目录的绝对路径
    current_dir = os.path.abspath(".")
    vbs_path = os.path.join(current_dir, "start_recruitflow.vbs")
    
    shell = Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.Targetpath = vbs_path
    shortcut.WorkingDirectory = current_dir
    shortcut.IconLocation = "C:\\Windows\\System32\\shell32.dll, 44"
    shortcut.save()
    
    print(f"✓ 桌面快捷方式已创建：{shortcut_path}")
    print(f"  目标：{vbs_path}")
    
except ImportError as e:
    print("缺少必要的库，请先安装：")
    print("  pip install pywin32")
    print(f"错误：{e}")
    sys.exit(1)
except Exception as e:
    print(f"创建快捷方式失败：{e}")
    sys.exit(1)




创建 RecruitFlow 桌面快捷方式
"""
import os
import sys

# 设置输出编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    from win32com.client import Dispatch
    
    # 获取桌面路径（不依赖 winshell）
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.exists(desktop):
        # 尝试使用公共桌面
        desktop = os.path.join(os.environ.get("PUBLIC", ""), "Desktop")
    
    shortcut_path = os.path.join(desktop, "RecruitFlow 启动.lnk")
    
    # 获取当前脚本所在目录的绝对路径
    current_dir = os.path.abspath(".")
    vbs_path = os.path.join(current_dir, "start_recruitflow.vbs")
    
    shell = Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.Targetpath = vbs_path
    shortcut.WorkingDirectory = current_dir
    shortcut.IconLocation = "C:\\Windows\\System32\\shell32.dll, 44"
    shortcut.save()
    
    print(f"✓ 桌面快捷方式已创建：{shortcut_path}")
    print(f"  目标：{vbs_path}")
    
except ImportError as e:
    print("缺少必要的库，请先安装：")
    print("  pip install pywin32")
    print(f"错误：{e}")
    sys.exit(1)
except Exception as e:
    print(f"创建快捷方式失败：{e}")
    sys.exit(1)


创建 RecruitFlow 桌面快捷方式
"""
import os
import sys

# 设置输出编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    from win32com.client import Dispatch
    
    # 获取桌面路径（不依赖 winshell）
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.exists(desktop):
        # 尝试使用公共桌面
        desktop = os.path.join(os.environ.get("PUBLIC", ""), "Desktop")
    
    shortcut_path = os.path.join(desktop, "RecruitFlow 启动.lnk")
    
    # 获取当前脚本所在目录的绝对路径
    current_dir = os.path.abspath(".")
    vbs_path = os.path.join(current_dir, "start_recruitflow.vbs")
    
    shell = Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.Targetpath = vbs_path
    shortcut.WorkingDirectory = current_dir
    shortcut.IconLocation = "C:\\Windows\\System32\\shell32.dll, 44"
    shortcut.save()
    
    print(f"✓ 桌面快捷方式已创建：{shortcut_path}")
    print(f"  目标：{vbs_path}")
    
except ImportError as e:
    print("缺少必要的库，请先安装：")
    print("  pip install pywin32")
    print(f"错误：{e}")
    sys.exit(1)
except Exception as e:
    print(f"创建快捷方式失败：{e}")
    sys.exit(1)



