#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 dump_ctrl_tree 装饰器的增强功能
"""

from winauto_helper import WinAuto

# 测试步骤
if __name__ == "__main__":
    print("开始测试 dump_ctrl_tree 装饰器...")
    
    # 初始化 WinAuto 对象
    bot = WinAuto(r"D:\Program Files\CBIM\modulelogin.exe")
    
    # 启动应用
    bot.start()
    
    # 获取登录窗口 - 这会触发 dump_ctrl_tree 装饰器
    login_window = bot.get_window(class_name='LoginDialog')
    
    if login_window:
        print("\n测试成功！控件树已保存到 reports 目录下的 Markdown 文件中。")
    else:
        print("\n测试失败！未能获取登录窗口。")
    
    # 关闭应用
    bot.close_app()
    
    print("\n测试结束。")
