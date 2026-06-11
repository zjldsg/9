import os
import subprocess
import sys
import shutil
from pathlib import Path

# ================= 配置区域 =================
# 1. 设置待处理的 APK 路径 (请确保路径正确)
APK_PATH = r"C:\Users\mac\Downloads\nowinandroid-main\nowinandroid-main\app\build\outputs\apk\demo\debug\app-demo-debug.apk"

# 2. 设置工具路径 (请根据实际存放位置修改)
# 假设 apktool.jar, zipalign.exe, apksigner.bat 位于脚本同级的 tools 文件夹内
SCRIPT_DIR = Path(__file__).parent
APKTOOL_JAR = SCRIPT_DIR / "tools" / "apktool.jar"
ZIPALIGN_EXE = SCRIPT_DIR / "tools" / "zipalign.exe"
APKSIGNER_BAT = SCRIPT_DIR / "tools" / "apksigner.bat"

# 3. 设置工作目录和输出文件名
BASE_NAME = Path(APK_PATH).stem
WORK_DIR = SCRIPT_DIR / f"{BASE_NAME}_decompiled"
SIGNED_APK = SCRIPT_DIR / f"{BASE_NAME}_modified_signed.apk"
KEYSTORE = "debug.keystore"  # 使用默认的 debug 密钥，或者替换为你的
KEY_ALIAS = "androiddebugkey"
STORE_PASS = "android"
KEY_PASS = "android"

def run_command(cmd, cwd=None, shell=True):
    """执行系统命令并打印输出"""
    print(f"[*] 执行命令: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    result = subprocess.run(cmd, cwd=cwd, shell=shell, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[X] 命令执行失败: {result.stderr}")
        sys.exit(1)
    else:
        print(result.stdout)
    return result.stdout

def decompile_apk():
    print("[*] 步骤 1: 正在解包 APK...")
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    run_command(f'java -jar "{APKTOOL_JAR}" d "{APK_PATH}" -o "{WORK_DIR}"')
    print("[√] 解包完成。\n")

def modify_smali():
    print("[*] 步骤 2: 正在修改 Smali 代码...")
    
    # 查找 smali 目录 (根据文档，通常是 smali 或 smali_classes1 等)
    smali_dirs = list(WORK_DIR.glob("smali*"))
    if not smali_dirs:
        print("[X] 未找到 Smali 目录，请检查解包结果。")
        sys.exit(1)
        
    target_dir = smali_dirs[0]
    
    # --- 修改逻辑示例：查找 MainActivity 并在 onCreate 中添加 Log ---
    # 根据 NowInAndroid 项目结构，主 Activity 可能是 MainActivity
    # 我们将在 onCreate 中添加 Log.d("NowInAndroid_Mod", "Hooked by APKTool!");
    
    # 查找 MainActivity.smali
    main_smali = None
    for smali_file in target_dir.rglob("MainActivity.smali"):
        if smali_file.exists():
            main_smali = smali_file
            break
            
    if not main_smali:
        print(f"[-] 未找到 MainActivity.smali，将在 {target_dir} 中随机修改一个文件作为演示。")
        # 如果找不到 MainActivity，找一个 .smali 文件
        smali_files = list(target_dir.rglob("*.smali"))
        if smali_files:
            main_smali = smali_files[0]
        else:
            print("[X] 未找到任何 .smali 文件！")
            sys.exit(1)

    print(f"[*] 修改文件: {main_smali}")

    with open(main_smali, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 寻找 onCreate 方法
    in_on_create = False
    insert_index = -1

    for i, line in enumerate(lines):
        if ".method" in line and "onCreate" in line and "Landroid/os/Bundle;" in line:
            in_on_create = True
        if in_on_create and ".locals" in line:
            # 获取本地寄存器数量
            try:
                reg_count = int(line.split(".locals")[1].strip())
                # 增加寄存器数量以容纳新变量
                lines[i] = f"    .locals {reg_count + 2}\n"
            except:
                pass
        if in_on_create and "invoke-super" in line and "onCreate" in line:
            # 在调用父类 onCreate 后插入代码
            insert_index = i + 1
            break

    if insert_index == -1:
        # 如果没找到合适的位置，就在方法末尾插入
        for i in range(len(lines)-1, 0, -1):
            if ".end method" in lines[i]:
                insert_index = i
                break

    if insert_index != -1:
        # 插入 Smali 代码：Log.d("NowInAndroid_Mod", "Hooked!");
        # v0, v1 是寄存器
        hook_code = [
            "    const-string v0, \"NowInAndroid_Mod\"\n",
            "    const-string v1, \"Hooked by APKTool Script!\"\n",
            "    invoke-static {v0, v1}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I\n",
            "    move-result v0\n", # 忽略返回值，只是为了占位
            "\n"
        ]
        lines[insert_index:insert_index] = hook_code

        with open(main_smali, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print("[√] Smali 修改完成 (已插入 Log Hook)。\n")
    else:
        print("[!] 警告：未能自动插入代码，请手动检查 Smali 文件。\n")

def rebuild_apk():
    print("[*] 步骤 3: 正在重新打包 APK...")
    unsigned_apk = SCRIPT_DIR / f"{BASE_NAME}_unsigned.apk"
    run_command(f'java -jar "{APKTOOL_JAR}" b "{WORK_DIR}" -o "{unsigned_apk}"')
    return unsigned_apk

def align_and_sign(unsigned_apk):
    print("[*] 步骤 4: 正在对齐和签名...")
    
    aligned_apk = SCRIPT_DIR / f"{BASE_NAME}_aligned.apk"
    
    # 1. 对齐 (Zipalign)
    print("[*] 4.1: 执行 Zipalign...")
    run_command(f'"{ZIPALIGN_EXE}" -v 4 "{unsigned_apk}" "{aligned_apk}"')
    
    # 2. 签名 (Apksigner)
    print("[*] 4.2: 执行 Apksigner...")
    sign_cmd = [
        "cmd", "/c", f'"{APKSIGNER_BAT}"', "sign",
        f"--ks={KEYSTORE}",
        f"--ks-key-alias={KEY_ALIAS}",
        f"--ks-pass=pass:{STORE_PASS}",
        f"--key-pass=pass:{KEY_PASS}",
        f"--out={SIGNED_APK}",
        f'"{aligned_apk}"'
    ]
    # 将列表转换为字符串执行 (Windows 兼容性更好)
    cmd_str = " ".join(sign_cmd)
    run_command(cmd_str)
    
    print(f"[√] 签名完成。最终文件: {SIGNED_APK}\n")

def install_apk():
    print("[*] 步骤 5: 正在安装到设备 (如果已连接)...")
    devices = subprocess.run('adb devices', shell=True, capture_output=True, text=True)
    if "device" in devices.stdout:
        run_command(f'adb install -r "{SIGNED_APK}"')
        print("[√] 安装完成！请在手机上查看应用。")
        print("[*] 提示：打开应用后，你可以通过 'adb logcat | grep NowInAndroid_Mod' 查看我们插入的日志。")
    else:
        print("[!] 未检测到连接的设备，请手动安装生成的 APK。")

def main():
    print("=== NowInAndroid APK 逆向工程大作业脚本 ===\n")
    
    # 检查 APK 文件是否存在
    if not Path(APK_PATH).exists():
        print(f"[X] 错误：找不到 APK 文件，请检查路径: {APK_PATH}")
        sys.exit(1)
        
    try:
        decompile_apk()
        modify_smali()
        unsigned_apk = rebuild_apk()
        align_and_sign(unsigned_apk)
        install_apk()
    except Exception as e:
        print(f"[X] 发生错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()