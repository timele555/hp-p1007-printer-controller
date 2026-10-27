NOTICE / 版权与许可说明
========================

1. 本仓库中的代码（app.py、spooler.py、selftest.py、scripts/ 下的脚本）
   为原创作品，以 MIT 许可证发布，见 LICENSE。

2. HP 打印机驱动与固件不在本仓库中。
   HP LaserJet P1000-P1500 Hostbased Plug and Play Basic Driver（含打印机
   固件 .img 文件）是 Hewlett-Packard Company 的专有软件，其 End User License
   Agreement 不授予公开再分发的权利，因此本仓库不包含、也不镜像任何 HP
   驱动或固件二进制。scripts/get-driver.ps1 只从 HP 官方分发服务器
   （ftp.hp.com）下载原始安装包，并用 SHA256 与数字签名双重校验其完整性。

3. 商标声明。HP、Hewlett-Packard、LaserJet 是 HP Inc. 的商标或注册商标。
   本项目与 HP Inc. 无任何隶属或背书关系，仅为其打印机的用户侧辅助工具。

4. 若你自行分发本仓库的衍生作品，请同样遵守上述第 2 条：不要将 HP
   驱动/固件二进制（.exe/.cab/.img/.dll/.cat 等）混入你的发行物。
