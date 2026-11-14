import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# --- CẤU HÌNH GIAO DIỆN CHUẨN HỌC THUẬT ---
def setup_academic_style():
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    plt.rcParams.update({
        'font.family': 'serif',
        'font.size': 11,
        'axes.labelsize': 12,
        'axes.titlesize': 13,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'legend.fontsize': 10,
        'figure.dpi': 300,
        'savefig.dpi': 300,
        'axes.edgecolor': '#333333',
        'axes.linewidth': 0.8
    })

def load_and_preprocess_data(nam_path='nam_results.csv', son_path='son_results.csv'):
    """Đọc và gộp dữ liệu từ 2 file CSV của Nam và Sơn."""
    try:
        df_nam = pd.read_csv(nam_path)
        df_nam['Author'] = 'Nam'
    except FileNotFoundError:
        print(f"Cảnh báo: Không tìm thấy file {nam_path}. Đang tạo dữ liệu mẫu cho Nam...")
        df_nam = generate_mock_data('Nam')

    try:
        df_son = pd.read_csv(son_path)
        df_son['Author'] = 'Sơn'
    except FileNotFoundError:
        print(f"Cảnh báo: Không tìm thấy file {son_path}. Đang tạo dữ liệu mẫu cho Sơn...")
        df_son = generate_mock_data('Sơn')

    df_combined = pd.concat([df_nam, df_son], ignore_index=True)
    return df_combined

def generate_mock_data(author_name):
    """Tạo dữ liệu mẫu để kiểm thử nếu chưa có file CSV thực tế."""
    np.random.seed(42 if author_name == 'Nam' else 123)
    payloads = [64, 128, 256, 512, 1024, 2048]
    data = []
    for p in payloads:
        base_throughput = 1000 - p * 0.2 if author_name == 'Nam' else 950 - p * 0.15
        base_latency = 5 + p * 0.01 if author_name == 'Nam' else 4 + p * 0.008
        
        for _ in range(50): # 50 samples cho mỗi payload để vẽ boxplot
            throughput = np.random.normal(base_throughput, 20)
            latency = np.random.normal(base_latency, 0.5)
            data.append({
                'payload_size': p,
                'throughput': max(10, throughput),
                'latency': max(0.5, latency)
            })
    return pd.DataFrame(data)

def plot_throughput_vs_payload(df):
    """Biểu đồ (1): Throughput vs Payload size"""
    fig, ax = plt.subplots(figsize=(7, 4.5))
    
    # Vẽ lineplot với độ lệch chuẩn (ci/error band)
    sns.lineplot(
        data=df, 
        x='payload_size', 
        y='throughput', 
        hue='Author', 
        style='Author',
        markers=['o', 's'], 
        dashes=False,
        linewidth=1.5,
        markersize=6,
        palette='tab10',
        ax=ax
    )
    
    ax.set_title('Throughput Performance Comparison')
    ax.set_xlabel('Payload Size (bytes)')
    ax.set_ylabel('Throughput (Mbps / ops/sec)')
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(title='Implementation', frameon=True, facecolor='white', framealpha=0.9)
    
    plt.tight_layout()
    plt.savefig('throughput_vs_payload.pdf', bbox_inches='tight')
    plt.savefig('throughput_vs_payload.png', bbox_inches='tight')
    print("Đã lưu biểu đồ: throughput_vs_payload.pdf/.png")
    plt.close()

def plot_latency_boxplot(df):
    """Biểu đồ (2): Boxplot phân bố Latency theo Payload size và Author"""
    fig, ax = plt.subplots(figsize=(8, 4.5))
    
    sns.boxplot(
        data=df,
        x='payload_size',
        y='latency',
        hue='Author',
        palette='Set2',
        ax=ax,
        fliersize=3,
        linewidth=1.0
    )
    
    ax.set_title('Latency Distribution across Payload Sizes')
    ax.set_xlabel('Payload Size (bytes)')
    ax.set_ylabel('Latency (ms)')
    ax.grid(True, linestyle='--', alpha=0.5, axis='y')
    ax.legend(title='Implementation', frameon=True, facecolor='white', framealpha=0.9)
    
    plt.tight_layout()
    plt.savefig('latency_boxplot.pdf', bbox_inches='tight')
    plt.savefig('latency_boxplot.png', bbox_inches='tight')
    print("Đã lưu biểu đồ: latency_boxplot.pdf/.png")
    plt.close()

if __name__ == '__main__':
    setup_academic_style()
    print("Đang đọc dữ liệu benchmark...")
    df = load_and_preprocess_data('nam_results.csv', 'son_results.csv')
    
    print("Đang vẽ biểu đồ Throughput...")
    plot_throughput_vs_payload(df)
    
    print("Đang vẽ biểu đồ Boxplot Latency...")
    plot_latency_boxplot(df)
    
    print("Hoàn tất! Các file đồ họa đã sẵn sàng đưa vào báo cáo/paper.")