PROJECT_TITLE = "基于 YOLO 的嵌入式果蔬识别与零售计价系统"
DEFAULT_CONFIG_PATH = "config.yaml"

# Mock 闭环专用的测试商品 label：MockFruitVegetableDetector 固定返回它，
# init_db 把它作为唯一默认种子商品。刻意用 mock_* 命名而非真实水果名，
# 避免测试交易与真实交易数据混淆。
MOCK_PRODUCT_LABEL = "mock_item"
MOCK_PRODUCT_NAME_CN = "测试商品"
