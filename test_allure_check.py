import subprocess
import os

def check_allure_available():
    """检查 Allure 命令行工具是否可用"""
    try:
        # 测试 subprocess.run 方式
        print("测试 subprocess.run 方式...")
        result = subprocess.run(["allure", "--version"], 
                               check=True, 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE, 
                               text=True)
        print(f"subprocess.run 成功: {result.stdout.strip()}")
        
        # 测试 os.system 方式
        print("\n测试 os.system 方式...")
        result = os.system("allure --version")
        print(f"os.system 成功: 返回码 {result}")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"subprocess.CalledProcessError: {e}")
        print(f" stdout: {e.stdout}")
        print(f" stderr: {e.stderr}")
    except FileNotFoundError as e:
        print(f"FileNotFoundError: {e}")
    except Exception as e:
        print(f"其他异常: {type(e).__name__}: {e}")
    
    return False

# 执行测试
if __name__ == "__main__":
    print("开始测试 Allure 工具检测...")
    result = check_allure_available()
    print(f"\n最终结果: {result}")
