import subprocess
import sys
import webbrowser
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('run_tests.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class TestRunnerConfig:
    """测试运行器配置类"""
    def __init__(self):
        self.reports_dir = Path("reports")
        self.allure_result_dir = self.reports_dir / "allure"
        self.allure_html_dir = self.reports_dir / "allure-html"
        self.html_report_path = self.reports_dir / "test_report.html"
        self.test_dir = "tests/"
        self.generate_allure = True
        self.open_report = True
        self.clean_allure = True


class TestRunner:
    """测试运行器类"""
    
    def __init__(self, config: Optional[TestRunnerConfig] = None):
        """初始化测试运行器
        
        Args:
            config: 测试运行器配置，默认使用默认配置
        """
        self.config = config or TestRunnerConfig()
        # 确保报告目录存在
        self.config.reports_dir.mkdir(exist_ok=True)
    
    def check_allure_available(self) -> bool:
        """检查 Allure 命令行工具是否可用
        
        Returns:
            bool: 如果 Allure 可用返回 True，否则返回 False
        """
        try:
            result = subprocess.run(
                ["allure", "--version"],
                capture_output=True,
                text=True,
                shell=True  # Windows 下需要 shell=True
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"检查 Allure 可用性失败: {e}")
            return False
    
    def generate_allure_report(self) -> bool:
        """生成 Allure HTML 报告
        
        Returns:
            bool: 如果报告生成成功返回 True，否则返回 False
        """
        # 检查 Allure 结果目录是否存在和非空
        if not self.config.allure_result_dir.exists():
            logger.warning(f"Allure 结果目录不存在: {self.config.allure_result_dir}")
            return False
        
        if not any(self.config.allure_result_dir.iterdir()):
            logger.warning(f"Allure 结果目录为空: {self.config.allure_result_dir}")
            return False
        
        logger.info("正在生成 Allure 报告...")
        
        # 构建 Allure 生成命令
        cmd = [
            "allure", "generate",
            str(self.config.allure_result_dir),
            "-o", str(self.config.allure_html_dir)
        ]
        
        if self.config.clean_allure:
            cmd.append("--clean")
        
        logger.info(f"执行命令: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                shell=True  # Windows 下需要 shell=True
            )
            
            if result.returncode == 0:
                logger.info("Allure 报告生成成功！")
                logger.info(f"报告路径: {self.config.allure_html_dir / 'index.html'}")
                return True
            else:
                logger.error(f"Allure 报告生成失败: 返回码 {result.returncode}")
                logger.error(f"错误输出: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"生成 Allure 报告时发生异常: {e}")
            return False
    
    def open_allure_report(self) -> bool:
        """在默认浏览器中打开 Allure 报告
        
        Returns:
            bool: 如果报告打开成功返回 True，否则返回 False
        """
        # 首先尝试使用 allure serve 命令
        logger.info("使用 allure serve 命令启动报告服务器...")
        
        cmd = [
            "allure", "serve",
            str(self.config.allure_result_dir),
            "-o", str(self.config.allure_html_dir)
        ]
        
        if self.config.clean_allure:
            cmd.append("--clean")
        
        logger.info(f"执行命令: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                shell=True  # Windows 下需要 shell=True
            )
            
            if result.returncode == 0:
                logger.info("Allure 报告已通过 allure serve 打开")
                return True
            else:
                logger.warning(f"使用 allure serve 打开报告失败: 返回码 {result.returncode}")
                logger.warning(f"错误输出: {result.stderr}")
        except Exception as e:
            logger.error(f"使用 allure serve 打开报告时发生异常: {e}")
        
        # 如果 allure serve 失败，尝试直接打开 HTML 文件
        logger.info("尝试直接打开 HTML 报告...")
        report_path = self.config.allure_html_dir / "index.html"
        
        if report_path.exists():
            logger.info(f"正在打开报告: {report_path}")
            try:
                webbrowser.open(f"file://{report_path}")
                return True
            except Exception as e:
                logger.error(f"直接打开报告失败: {e}")
                return False
        else:
            logger.error(f"报告文件不存在: {report_path}")
            return False
    
    def run_tests(self) -> int:
        """运行测试并生成报告
        
        Returns:
            int: 测试执行的返回码，0 表示成功，非 0 表示失败
        """
        logger.info("=" * 70)
        logger.info("开始执行测试...")
        logger.info("=" * 70)
        
        # 构建测试命令
        test_cmd = [
            "pytest", self.config.test_dir,
            f"--html={self.config.html_report_path}",
            "--self-contained-html",
            "-v"
        ]
        
        # 如果需要生成 Allure 报告，添加 Allure 参数
        if self.config.generate_allure:
            test_cmd.extend([
                f"--alluredir={self.config.allure_result_dir}",
                "--clean-alluredir"
            ])
        
        logger.info(f"执行测试命令: {' '.join(test_cmd)}")
        
        # 运行测试
        result = subprocess.run(test_cmd, shell=True)  # Windows 下需要 shell=True
        
        logger.info("\n" + "=" * 70)
        
        if result.returncode == 0:
            logger.info("测试执行成功！")
            logger.info(f"HTML 报告已生成: {self.config.html_report_path}")
            
            # 如果需要生成 Allure 报告且 Allure 可用，则生成报告
            if self.config.generate_allure:
                if self.check_allure_available():
                    logger.info("\n发现 Allure 命令行工具，正在生成 Allure 报告...")
                    if self.generate_allure_report() and self.config.open_report:
                        self.open_allure_report()
                else:
                    logger.info("\n[提示] 若要生成 Allure 报告，可安装 Allure 命令行工具:")
                    logger.info("  安装方式: https://allurereport.org/docs/gettingstarted/installation/")
                    logger.info(f"  手动生成命令: allure generate {self.config.allure_result_dir} -o {self.config.allure_html_dir} --clean")
        else:
            logger.error(f"测试执行失败！返回码: {result.returncode}")
            logger.info(f"HTML 报告已生成: {self.config.html_report_path}")
        
        logger.info("=" * 70)
        return result.returncode


def main():
    """主函数"""
    # 创建测试运行器实例
    runner = TestRunner()
    # 运行测试
    return runner.run_tests()


if __name__ == "__main__":
    sys.exit(main())