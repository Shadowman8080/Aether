$ErrorActionPreference = 'Stop'
$vbox = Join-Path $env:ProgramFiles 'Oracle\VirtualBox\VBoxManage.exe'
if (-not (Test-Path -LiteralPath $vbox)) { throw 'Install VirtualBox first, then run this script again.' }
$name = 'Aether Linux 0.2.1 UEFI'
$disk = Join-Path $PSScriptRoot 'aether-0.2.1-x86_64.vmdk'
$share = Join-Path $PSScriptRoot 'Aether-Shared-Test'
$vmFolder = Join-Path $PSScriptRoot 'Aether-VirtualBox'
if (-not (Test-Path -LiteralPath $disk)) { throw 'Keep this script beside the Aether 0.2.1 VMDK.' }
$existing = & $vbox list vms
if ($LASTEXITCODE -ne 0) { throw 'Could not list VirtualBox machines.' }
if ($existing -match [regex]::Escape('"' + $name + '"')) { throw "A VM named $name already exists. No changes were made." }
if (Test-Path -LiteralPath $vmFolder) { throw 'The Aether-VirtualBox folder already exists. No changes were made.' }
function Invoke-VBox {
    & $vbox @args
    if ($LASTEXITCODE -ne 0) { throw "VirtualBox command failed: $($args[0])" }
}
New-Item -ItemType Directory -Path $vmFolder | Out-Null
New-Item -ItemType Directory -Force -Path $share | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $share 'host-marker.txt'))) {
    Set-Content -LiteralPath (Join-Path $share 'host-marker.txt') -Value 'Aether shared-folder test from Windows.' -Encoding ascii
}
$vmDisk = Join-Path $vmFolder 'aether.vdi'
Invoke-VBox clonemedium disk $disk $vmDisk --format VDI
Invoke-VBox createvm --name $name --ostype Linux_64 --basefolder $vmFolder --register
Invoke-VBox modifyvm $name --memory 3072 --cpus 4 --firmware efi --graphicscontroller vmsvga --vram 128 --accelerate3d off --nic1 nat --nictype1 82540EM --clipboard-mode bidirectional --boot1 disk --boot2 none --boot3 none --boot4 none
Invoke-VBox storagectl $name --name SATA --add sata --controller IntelAhci
Invoke-VBox storageattach $name --storagectl SATA --port 0 --device 0 --type hdd --medium $vmDisk
Invoke-VBox sharedfolder add $name --name AetherTest --hostpath $share
Write-Output "Created $name. Start it in VirtualBox, log in as aether, and run startx."
