
**To run optimization tests:**
1. Edit parameters: `generate_configs.sh`
2. Submit: `bash submit_tests.sh [question_file]`
3. Monitor: `tail -f logs/detailed_*.log`
4. Analyze: `column -t -s',' logs/timing_summary.csv`


### **Basic Usage (Default Settings)**

```bash
cd /path/to/ai-cosci-all 
bash /path/to/submit_tests.sh
```

This will:
1. Generate configurations from `/tmp/generate_configs.sh`
2. Create `configs/optimization_jobs.txt`
3. Submit SLURM array job
4. Run all configurations in parallel

### **With Custom Question**

```bash
bash /tmp/submit_tests.sh relative_path_from_main/to/my_question.txt
```
