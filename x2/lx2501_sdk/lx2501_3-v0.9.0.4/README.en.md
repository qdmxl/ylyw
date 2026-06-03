# QuickStart of AgiBot X2 AimDK

## Documentations

The docs for sencondary development is published in 2 modes:
- [Local Docs](docs/cn/_build/html) - static, distributed with this SDK package.
- [Online Docs](https://x2-aimdk.agibot.com) - dyanmic, always up to date.

### Local Docs Usage

To access local docs (Assume port 5789 is available):

1. Start a local webserver:

```bash
sh ./run_docs.sh 5789
```

2. Then visit <http://127.0.0.1:5789> in your browser

**Note: up-to-date online docs are always preferred**

### Online Docs Usage (recommended)

Please visit <https://x2-aimdk.agibot.com> in your browser and select
the docs with matching version


## AimDK interfaces & examples

Please refer to the docs.

## Non-volatile User Data

The disks in the robot would be reformated during firmware upgrade/downgrade.

To make your data survive:
1. put you data under `$HOME`(/agibot/data/home/agi), where data are non-volatile by default, except:
   + DO NOT save data into `$HOME/aimdk*`, these are preserved and maintained by the system.
   + BE CAREFUL of features like factory reset, which would force erasing all data.
2. backup is always recommended, at least before firmware upgrade/downgrade
