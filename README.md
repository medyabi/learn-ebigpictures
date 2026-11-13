# learn.ebigpictures.com

Static site for the Windows Server labs, built from:
- https://github.com/medyabi/windows-server2025-Hybrid-lab
- https://github.com/medyabi/windows-server-security-lab

Rebuild after changing a lab repo:

```bash
pip install markdown
git clone https://github.com/medyabi/windows-server2025-Hybrid-lab hybrid
git clone https://github.com/medyabi/windows-server-security-lab security
python3 tools/build.py hybrid security .
```
