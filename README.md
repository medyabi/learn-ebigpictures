# learn.ebigpictures.com

Static site for the Windows Server labs, built from:
- https://github.com/medyabi/windows-server2025-Hybrid-lab
- https://github.com/medyabi/windows-server-security-lab
- https://github.com/medyabi/Azure-Local-Lab-Deployment-Guide (split into one page per phase)

Rebuild after changing a lab repo:

```bash
pip install markdown
git clone https://github.com/medyabi/windows-server2025-Hybrid-lab hybrid
git clone https://github.com/medyabi/windows-server-security-lab security
git clone https://github.com/medyabi/Azure-Local-Lab-Deployment-Guide azurelocal
python3 tools/build.py hybrid security azurelocal .
```
