p=$(cat problems/ex2.txt)
python -m src.cli \
  --question "$p" \
  --subtask-centric \
  --verbose \
  --output tests/q2.md \
  --input-dir data/Q2 