"""
Run once after first docker compose up:
  docker exec mediroute_backend python seed.py
"""
import subprocess, sys, os

scripts = [
    "ml_training/generate_synthetic.py",
    "ml_training/generate_dataset.py", 
    "ml_training/train_model.py",
]

for s in scripts:
    print(f"\n{'='*50}\nRunning {s}\n{'='*50}")
    result = subprocess.run([sys.executable, s], cwd="/app")
    if result.returncode != 0:
        print(f"FAILED: {s}")
        sys.exit(1)

print("\n✅ Seed complete")
