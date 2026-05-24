#!/bin/bash
# Master pipeline: translator + generator + auto-commit. Survives restarts.
set -u
cd /Users/vladys/Proyectos/youtube-bot
set -a; source .env; set +a

LOG_DIR=/tmp/yb_pipeline
mkdir -p $LOG_DIR
MASTER_LOG=$LOG_DIR/master.log

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a $MASTER_LOG; }

log "===== MASTER PIPELINE START ====="

# Auto-commit every 10 min in background
(
while true; do
  sleep 600
  cd /Users/vladys/Proyectos/youtube-bot
  CHANGES=$(git status -s scripts/ | wc -l | tr -d ' ')
  if [ "$CHANGES" != "0" ]; then
    git add scripts/ 2>/dev/null
    git commit -m "auto: pipeline progress $(date +%Y-%m-%d_%H:%M) — $CHANGES files

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>" 2>/dev/null
    git pull --rebase 2>/dev/null
    git push 2>/dev/null
    echo "[$(date +%H:%M:%S)] auto-committed $CHANGES files" >> $LOG_DIR/master.log
  fi
done
) &
COMMITTER_PID=$!
log "auto-committer PID=$COMMITTER_PID"

# Stage 1: translator with auto-restart
run_translator() {
  while true; do
    log "starting translator"
    python3 scripts/translate_scripts.py >> $LOG_DIR/translate.log 2>&1
    EC=$?
    log "translator exit=$EC"
    if [ $EC -eq 0 ]; then
      log "translator DONE"
      break
    fi
    log "translator died, restart in 60s"
    sleep 60
  done
}

# Stage 2: generator SAFE channels (no conflict)
run_gen_safe() {
  python3 -c "
import sys; sys.path.insert(0,'scripts')
import generate_content as gc
import os, time, json, logging
from pathlib import Path
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('gen_safe')
SAFE = ['dark_files','mind_wired','disaster_decode','cash_cafe','vidasana360','hogarinteligente']
progress = gc.load_progress()
for ch in SAFE:
    cfg = gc.CHANNELS[ch]
    used = set(progress.get(ch,{}).get('used_topics',[]))
    pool = [t for t in cfg['topics_pool'] if t not in used]
    log.info('=== %s: %d topics, target 30 ===', ch, len(pool))
    produced = 0
    for topic in pool:
        if produced >= 30: break
        try:
            log.info('[%s] %d/30: %s', ch, produced+1, topic[:60])
            script = gc.generate_one(ch, topic)
            idx = gc.next_index(ch)
            slug = gc.slugify(script.get('title', topic))
            fname = f'{idx:02d}_{slug}.json'
            path = Path('scripts')/ch/fname
            path.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding='utf-8')
            log.info('[%s] saved %s', ch, fname)
            progress.setdefault(ch,{}).setdefault('used_topics',[]).append(topic)
            progress[ch]['produced'] = progress[ch].get('produced',0)+1
            gc.save_progress(progress)
            produced += 1
            time.sleep(45)
        except Exception as e:
            log.error('FAIL %s/%s: %s', ch, topic[:40], str(e)[:120])
            time.sleep(60)
    log.info('--- %s done: %d ---', ch, produced)
log.info('SAFE COMPLETE')
" >> $LOG_DIR/gen_safe.log 2>&1
}

# Stage 3: generator POST channels (catbrothers/finanzas/salud) AFTER translator
run_gen_post() {
  python3 -c "
import sys; sys.path.insert(0,'scripts')
import generate_content as gc
import os, time, json, logging
from pathlib import Path
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('gen_post')
POST = ['catbrothers','finanzas_clara','salud_longevidad']
progress = gc.load_progress()
for ch in POST:
    cfg = gc.CHANNELS[ch]
    used = set(progress.get(ch,{}).get('used_topics',[]))
    pool = [t for t in cfg['topics_pool'] if t not in used]
    log.info('=== %s: %d topics, target 30 ===', ch, len(pool))
    produced = 0
    for topic in pool:
        if produced >= 30: break
        try:
            log.info('[%s] %d/30: %s', ch, produced+1, topic[:60])
            script = gc.generate_one(ch, topic)
            idx = gc.next_index(ch)
            slug = gc.slugify(script.get('title', topic))
            fname = f'{idx:02d}_{slug}.json'
            path = Path('scripts')/ch/fname
            path.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding='utf-8')
            log.info('[%s] saved %s', ch, fname)
            progress.setdefault(ch,{}).setdefault('used_topics',[]).append(topic)
            progress[ch]['produced'] = progress[ch].get('produced',0)+1
            gc.save_progress(progress)
            produced += 1
            time.sleep(45)
        except Exception as e:
            log.error('FAIL %s/%s: %s', ch, topic[:40], str(e)[:120])
            time.sleep(60)
    log.info('--- %s done: %d ---', ch, produced)
log.info('POST COMPLETE')
" >> $LOG_DIR/gen_post.log 2>&1
}

# Run translator + gen_safe in parallel (different APIs)
run_translator &
TRANS_PID=$!
log "translator launched PID=$TRANS_PID"

run_gen_safe &
GEN_SAFE_PID=$!
log "gen_safe launched PID=$GEN_SAFE_PID"

# Wait translator before launching gen_post
wait $TRANS_PID
log "translator finished, launching gen_post"

run_gen_post &
GEN_POST_PID=$!
log "gen_post launched PID=$GEN_POST_PID"

# Wait remaining
wait $GEN_SAFE_PID
log "gen_safe finished"
wait $GEN_POST_PID
log "gen_post finished"

# Final commit
cd /Users/vladys/Proyectos/youtube-bot
CHANGES=$(git status -s scripts/ | wc -l | tr -d ' ')
if [ "$CHANGES" != "0" ]; then
  git add scripts/
  git commit -m "auto: pipeline FINAL — $CHANGES files

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
  git pull --rebase
  git push
  log "final commit pushed: $CHANGES files"
fi

log "===== MASTER PIPELINE COMPLETE ====="
kill $COMMITTER_PID 2>/dev/null
