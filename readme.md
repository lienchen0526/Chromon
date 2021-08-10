# Run

python src/chromo.py -y ./chromo.yaml

# Install as service (using [nssm](https://nssm.cc/download))

Template command
```
$env:BASE = "C:\Users\victim-entry\Chromon";
.\nssm.exe install Chromon (get-command python).source "$env:BASE\src\chromo.py -y $env:BASE\chromo.yaml";
.\nssm.exe start Chromon
```