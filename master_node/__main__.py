import argparse
from pathlib import Path

from master_node.http_server import run_http_server


if __name__ == "__main__":
    run_http_server(9001)