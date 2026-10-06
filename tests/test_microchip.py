import gzip
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('microchip_export',ROOT/'scripts/export-microchip.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class Microchip(unittest.TestCase):
    def test_target_mapping(self):
        env=dict(os.environ,EDF_TARGET='mpfs-disco-kit')
        out=subprocess.check_output(['bash','-c',f'source "{ROOT}/config/targets.sh"; printf "%s\\n" "$EDF_VENDOR" "$LINUX_MACHINE" "$IMAGE_RECIPE" "$KERNEL_RECIPE" "$SOURCE_ROOT"'],env=env,text=True)
        self.assertEqual(out.splitlines(),['microchip','mpfs-disco-kit','mchp-base-image','linux-mchp','/home/amd-edf/microchip'])

    def test_export_preserves_vendor_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);deploy=root/'deploy';deploy.mkdir();sdk=root/'sdk';sdk.mkdir()
            stem='mchp-base-image-mpfs-disco-kit.rootfs-123'
            payload=b'MICROCHIP_NATIVE_DISK\0'*4096
            (deploy/(stem+'.wic')).write_bytes(payload)
            (deploy/'mchp-base-image-mpfs-disco-kit.rootfs.wic').symlink_to(stem+'.wic')
            for name in (stem+'.tar.gz',stem+'.manifest','fitImage','payload.bin','boot.scr'):
                (deploy/name).write_bytes(b'test-input')
            settings={'MACHINE':'mpfs-disco-kit','DEPLOY_DIR_IMAGE':str(deploy),'IMAGE_LINK_NAME':'mchp-base-image-mpfs-disco-kit.rootfs','DEPLOY_DIR_SDK':str(sdk)}
            raw_run=mod.common.run
            def fake_run(*args,**kwargs):
                if args[0]=='bitbake':return subprocess.CompletedProcess(args,0,stdout='\n'.join(f'{k}="{v}"' for k,v in settings.items()))
                if args[0]=='bmaptool':Path(args[3]).write_text('fixture-blockmap');return
                if 'manifest' in args:Path(args[-1]).write_text('<manifest/>');return
                return raw_run(*args,**kwargs)
            with patch.dict(os.environ,EDF_TARGET='mpfs-disco-kit',IMAGE_RECIPE='mchp-base-image',SOURCE_ROOT=str(root)), patch.object(mod.common,'run',side_effect=fake_run):
                mod.main(root,root/'out')
            out=next((root/'out/mpfs-disco-kit').iterdir())
            self.assertEqual(gzip.decompress((out/'sdcard.wic.gz').read_bytes()),payload)
            self.assertEqual((deploy/(stem+'.wic')).read_bytes(),payload)
            self.assertFalse((out/'boot.bin').exists())
            self.assertEqual(json.loads((out/'build-info.json').read_text())['vendor'],'microchip')
            self.assertTrue((out/'SHA256SUMS').is_file())

if __name__=='__main__':unittest.main()
