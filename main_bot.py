import sys
import time
import random
import traceback
import os
import bot_tools
from bot_tools import (
    BotPausedResumeHomeException,
    check_pause_point,
    smart_sleep,
    human_sleep,
    check_wrong_buttons_a14,
    double_click_storage_bars,
    ensure_return_to_home_page_a14,
    check_resources_full_for_upgrade,
    check_wall_resources_full_a14,
    BotState
)
from bot_upgrade import (
    run_a14_upgrade_loop,
    run_a14_wall_upgrade_loop
)
from bot_attack import execute_attack
from bot_id_switch import (
    load_id_memory,
    save_id_memory,
    get_id_role_label,
    switch_to_target_id
)

from flask import Flask, jsonify, send_from_directory
import threading

# ==========================================
# 1. BOT OPERATING MODE CONFIGURATION
# ==========================================

def select_bot_configuration():
    pass

# ==========================================
# 2. UPGRADE CHECK & EXECUTION HELPERS
# ==========================================

def check_and_run_building_upgrade():
    check_pause_point(allow_raise=True)
    check_wrong_buttons_a14()
    double_click_storage_bars()
    human_sleep(0.45, 0.08)
    if check_resources_full_for_upgrade():
        upgraded = run_a14_upgrade_loop()
        return bool(upgraded)
    return False

def check_and_run_wall_upgrade():
    check_pause_point(allow_raise=True)
    check_wrong_buttons_a14()
    double_click_storage_bars()
    human_sleep(0.45, 0.08)
    if check_wall_resources_full_a14():
        upgraded = run_a14_wall_upgrade_loop()
        return bool(upgraded)
    return False

def run_combined_building_then_wall_upgrade(loop_label="UPGRADE LOOP"):
    b_up = check_and_run_building_upgrade()
    human_sleep(0.6, 0.1)
    w_up = check_and_run_wall_upgrade()
    any_up = bool(b_up or w_up)
    return b_up, w_up, any_up

def run_n_fast_attacks_with_resume_memory(state_dict, target_attacks, phase_label="ATTACK SERIES"):
    while state_dict["attacks_done"] < target_attacks:
        check_pause_point(allow_raise=True)
        next_atk_num = state_dict["attacks_done"] + 1
        smart_sleep(random.uniform(1.0, 1.5))
        execute_attack(is_first_attack=(next_atk_num == 1))
        state_dict["attacks_done"] += 1

# ==========================================
# 3. MASTER LOOP CONTROLLER
# ==========================================

def run_coc_bot(api_mode, api_total_ids, api_start_id):
    bot_mode = str(api_mode)
    total_ids = int(api_total_ids)
    current_id = int(api_start_id)

    smart_sleep(random.uniform(1.5, 2.0))
    cycle_count = 1
    runtime_state = {
        "current_id": current_id,
        "phase": "START_CYCLE",
        "attacks_done": 0,
        "id_timer_start": None,
        "id_elapsed_sec": 0.0,
        "loop2_any_upgraded": False
    }

    while True:
        try:
            check_pause_point(allow_raise=True)
            active_id = runtime_state["current_id"]
            
            if bot_mode == "1":
                execute_attack(is_first_attack=(cycle_count == 1))
            elif bot_mode == "2":
                check_and_run_building_upgrade()
                smart_sleep(60.0)
            elif bot_mode == "3":
                check_and_run_wall_upgrade()
                smart_sleep(60.0)
            elif bot_mode == "4":
                if runtime_state["phase"] == "START_CYCLE":
                    run_combined_building_then_wall_upgrade()
                    runtime_state["phase"] = "ATTACK_10"
                    runtime_state["attacks_done"] = 0
                if runtime_state["phase"] == "ATTACK_10":
                    run_n_fast_attacks_with_resume_memory(runtime_state, target_attacks=10)
                    runtime_state["phase"] = "START_CYCLE"
                    runtime_state["attacks_done"] = 0
            elif bot_mode == "5":
                smart_sleep(60.0)
                next_id = (active_id % total_ids) + 1
                switch_to_target_id(next_id, total_ids, current_id_index=active_id)
                runtime_state["current_id"] = next_id
            elif bot_mode == "6":
                execute_attack(is_first_attack=(cycle_count == 1))
            elif bot_mode == "7":
                if runtime_state["phase"] == "START_CYCLE":
                    run_combined_building_then_wall_upgrade()
                    runtime_state["phase"] = "ATTACK_10"
                    runtime_state["attacks_done"] = 0
                if runtime_state["phase"] == "ATTACK_10":
                    run_n_fast_attacks_with_resume_memory(runtime_state, target_attacks=10)
                    runtime_state["phase"] = "SWITCH_ID"
                if runtime_state["phase"] == "SWITCH_ID":
                    next_id = (active_id % total_ids) + 1
                    switch_to_target_id(next_id, total_ids, current_id_index=active_id)
                    runtime_state["current_id"] = next_id
                    runtime_state["phase"] = "START_CYCLE"

            cycle_count += 1
            smart_sleep(random.uniform(3.0, 4.5))

        except BotPausedResumeHomeException:
            ensure_return_to_home_page_a14()
            continue
        except Exception as e:
            time.sleep(5)
            ensure_return_to_home_page_a14()

# ==========================================
# FLASK LOCAL API SERVER & WEB DASHBOARD
# ==========================================
app = Flask(__name__, static_folder='.')

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.route('/')
def serve_dashboard():
    return send_from_directory('.', 'index.html')

@app.route('/start/<int:mode>', methods=['GET'])
def api_start(mode):
    BotState.PAUSED = False
    BotState.STOPPED = False
    total_ids = 10
    start_id = 1
    print(f"\n[🌐 API TRIGGERED] Starting Mode [{mode}] | Total IDs: {total_ids}")
    threading.Thread(target=run_coc_bot, args=(mode, total_ids, start_id), daemon=True).start()
    return jsonify({"status": "Bot Started", "mode": mode})

@app.route('/pause', methods=['GET'])
def api_pause():
    BotState.PAUSED = True
    return jsonify({"status": "Paused"})

@app.route('/resume', methods=['GET'])
def api_resume():
    BotState.PAUSED = False
    return jsonify({"status": "Resumed"})

@app.route('/stop', methods=['GET'])
def api_stop():
    BotState.STOPPED = True
    return jsonify({"status": "Stopped"})

if __name__ == "__main__":
    print("==================================================")
    print("🌐 Local API Server Starting on http://127.0.0.1:5000")
    print("🚀 App और Browser से कमांड लेने के लिए तैयार!")
    print("==================================================")
    app.run(host='127.0.0.1', port=5000)
