#!/usr/bin/env bash
# Gokboru Hava Savunma Sistemi - Jetson Orin Nano kurulum script'i
#
# Bu, Faz 0/1'deki (bkz. README.md) scriptlenebilir adimlari otomatikler.
# PyTorch adimi OTOMATIK YAPILAMAZ: JetPack surumunuze ozel bir wheel
# NVIDIA'nin kendi sayfasindan elle indirilip kurulmali - script bunu
# ortada durdurup hatirlatir.
#
# Kullanim (Jetson'un kendi terminalinde, repo klonlandiktan sonra):
#   chmod +x jetson/setup_jetson.sh
#   ./jetson/setup_jetson.sh
#
# NOT: Bu script gercek bir Jetson'da TEST EDILMEDI (bu ortamda Jetson
# yok) - adim adim calistirip her ciktiyi kontrol edin, bir adim
# patlarsa (set -e) orada durur, bir sonraki adima gecmez.

set -e

echo "== [1/5] Jetson performans modu =="
sudo nvpmodel -m 0
sudo jetson_clocks

echo "== [2/5] Sistem paketleri =="
sudo apt update
sudo apt install -y git python3-pip v4l-utils

echo "== [3/5] Arduino seri port izni (dialout grubu) =="
sudo usermod -aG dialout "$USER"
echo "NOT: Bu degisikligin etkili olmasi icin oturumu kapatip tekrar acmaniz gerekebilir."

echo "== [4/5] Python bagimliliklari (torch haric) =="
pip3 install --upgrade pip
pip3 install ultralytics pyserial

cat <<'EOF'

====================================================================
DUR - ELLE YAPMANIZ GEREKEN TEK ADIM: PyTorch

pip'teki standart "torch" paketi Jetson'in ARM+CUDA mimarisiyle
calismaz (CPU-only kurulur ya da hic calismaz). JetPack surumunuzu
asagidakiyle kontrol edin:

    sudo apt show nvidia-jetpack | grep Version

Sonra NVIDIA'nin resmi Jetson gelistirici forumundaki / "Jetson AI Lab"
sayfasindaki "PyTorch for Jetson" basligindan, bulduğunuz JetPack
surumune uygun .whl dosyasini indirip kurun:

    pip3 install <indirdiginiz-dosya>.whl

Kurulumdan SONRA asagidakiyle dogrulayin:

    python3 -c "import torch; print(torch.cuda.is_available())"

Bu "True" yazdirmali. "False" veya hata aliyorsaniz yanlis wheel
kurulmus demektir - ultralytics/YOLO Jetson'in GPU'sunu kullanamaz,
cok yavas calisir.
====================================================================

EOF

echo "== [5/5] OpenCV kontrolu =="
python3 -c "import cv2; print('OpenCV surumu:', cv2.__version__)" || \
  echo "[UYARI] OpenCV import edilemedi. JetPack'in sistem OpenCV'sini kullanmak icin sanal ortami --system-site-packages ile kurdugunuzdan emin olun."

echo ""
echo "Kurulum tamamlandi. Simdi sirayla:"
echo "  python3 tools/test_camera.py"
echo "  python3 tools/test_serial.py"
echo "  python3 main.py"
