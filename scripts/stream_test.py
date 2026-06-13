import cv2
import time

print("📸 正在初始化 USB 摄像头...")
cap = cv2.VideoCapture(0)

# ⚠️ 依然强制降维！实时视频流对带宽压榨更恐怖，必须锁定 VGA 分辨率
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

if not cap.isOpened():
    print("❌ 无法打开摄像头，请检查 USB 连接。")
    exit()

print("✅ 摄像头已点亮！请看向树莓派的 7 寸屏幕或 VNC 桌面。")
print("💡 提示：在显示画面的窗口中，按下键盘的 'q' 键即可安全退出。")

fps_start_time = time.time()
frame_count = 0

while True:
    ret, frame = cap.read()
    if not ret:
        print("❌ 抓取画面失败，数据流中断！")
        break

    # 计算并显示实时 FPS
    frame_count += 1
    elapsed_time = time.time() - fps_start_time
    fps = frame_count / elapsed_time
    
    # 在画面左上角画出绿色的 FPS 数值
    cv2.putText(frame, f"FPS: {fps:.1f} (640x480)", (10, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    # 投射画面到屏幕
    cv2.imshow("Live Camera Stream", frame)

    # 1 毫秒刷新一次，并监听键盘输入，按 'q' 退出
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# 优雅释放硬件资源
cap.release()
cv2.destroyAllWindows()
print("🔌 视频流已关闭，硬件资源释放完毕。")