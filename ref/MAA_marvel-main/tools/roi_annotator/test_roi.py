from __future__ import annotations

import argparse
from pathlib import Path

from roi_manager import ROIManager


def main() -> None:
    parser = argparse.ArgumentParser(description="读取一个 ROI 配置")
    parser.add_argument("name")
    parser.add_argument("--db", default="ROI_DB")
    args = parser.parse_args()
    manager = ROIManager(args.db)
    config = manager.get_config(args.name)
    print("名称:", config["name"])
    print("ROI 坐标:", config["roi"])
    print("点击坐标:", manager.get_click_point(args.name))
    print("识别类型:", manager.get_type(args.name))


if __name__ == "__main__":
    main()
