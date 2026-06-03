#!/bin/bash

set -e
if [ $# -ne 1 ]; then
  echo 'usage: run.sh <port>'
  exit 1
fi

cd "$(dirname $0)/docs/cn/_build/html/"

# index
if [ ! -f index.html ];then
cat > index.html <<'EOF'
<html>
<head><script>
let lang=navigator.language.startsWith("zh")? "zh-cn":"en";
window.location.href=`${window.location.origin}/${lang}/latest/`;
</script></head>
<body></body>
</html>
EOF
fi
# make latest
for lang in ./*;do
  [ -d "${lang}" ] || continue
  if [ ! -d "${lang}/latest" ];then
    for obj in "${lang}"/*;do
      [ -d "${obj}" ] || continue
      echo "patching ${obj} as latest"
      ln -rs $obj "${lang}/latest" && break
    done
  fi
done

python3 -m http.server $1

# vim: ts=2 sts=2 sw=2 et
