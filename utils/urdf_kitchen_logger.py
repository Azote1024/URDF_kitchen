import logging
import sys
import os
from datetime import datetime

def setup_logger(name, log_file=None, level=logging.INFO):
    """
    ロガーをセットアップする関数
    
    Args:
        name (str): ロガーの名前
        log_file (str, optional): ログファイルのパス。指定しない場合は logs/ ディレクトリに自動生成
        level (int): ログレベル
        
    Returns:
        logging.Logger: 設定済みのロガー
    """
    # logsディレクトリの作成
    if not os.path.exists('logs'):
        os.makedirs('logs')
        
    if log_file is None:
        timestamp = datetime.now().strftime('%Y%m%d')
        log_file = os.path.join('logs', f'urdf_kitchen_{timestamp}.log')

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    handler = logging.FileHandler(log_file, encoding='utf-8')
    handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # ハンドラが重複して追加されないようにチェック
    if not logger.handlers:
        logger.addHandler(handler)
        logger.addHandler(console_handler)

    return logger
