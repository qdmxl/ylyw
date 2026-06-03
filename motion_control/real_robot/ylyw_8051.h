/**
 * ylyw_8051.h — YLYW运动控制推理引擎（8051定点版 v2）
 * 兼容Keil uVision2 (C51)，所有变量在函数开头声明
 *
 * 功能: 陀螺仪读数 → 六爻编码 → 卦象匹配 → 步态决策 → 24舵机
 *
 * 使用方法:
 *   1. main.c开头: #include "ylyw_8051.h"
 *   2. main()中先 initial_position(); 再 ylyw_init();
 *   3. while(1)调用 ylyw_main();
 */
#ifndef __YLYW_8051_H__
#define __YLYW_8051_H__

#include "basal.h"
#include "main.h"
#include "adc.h"
#include "REG15W4Kxx.h"

typedef unsigned char u8;
typedef unsigned int  u16;
typedef unsigned long u32;
typedef signed   short s16;

/* ============================================================
 * L1 八卦原型（8卦×6维，Flash, 48字节）
 * ============================================================ */
const u8 code TRIGRAM[8][6] = {
    {217,204,230,204, 38,179}, {179,102, 77,153,102,128},
    { 77,140,140, 64,217,153}, {242,166,191,242, 13,128},
    {140,153,128,128,102,230}, { 64, 89,102, 51,179,102},
    {166,179,153,166, 77,140}, {128,128,115,128,115,140},
};

/* ============================================================
 * L3 六十四卦爻模板（384字节 Flash）
 * ============================================================ */
const u8 code HEXAGRAM[64][6] = {
    {242,240,235,229,153,210},{ 31, 51, 38, 69, 64,109},
    {140,153,128,117,140,130},{110,120,113, 84,108, 99},
    {110,120,110, 84,108, 99},{134,153,138,117,139,158},
    { 58, 79, 62, 48, 87, 52},{128,153,128,117,125,122},
    {108,120,112, 84,108, 99},{108,120,110, 84,108, 99},
    {166,179,166,161,163,191},{235,210,166,237,247,143},
    {166,179,166,161,163,191},{201,201,204,179,117,189},
    {242,214,178,242,252,143},{191,204,201,163,173,191},
    {166,179,166,161,163,191},{123,130,120,112,139, 96},
    {128,153,128,117,125,122},{110,118,110, 84,109, 99},
    {201,201,204,179,117,189},{166,179,166,161,163,191},
    {122, 85,112, 87,140, 74},{ 57, 68, 54, 41, 66,108},
    {201,201,204,179,117,189},{128,153,128,117,125,122},
    {110,120,113, 84,108, 99},{ 57, 68, 54, 41, 66,108},
    { 49, 63, 51, 40, 51,108},{166,179,166,161,163,191},
    {128,153,128,117,125,122},{166,179,166,161,163,191},
    {201,201,204,179,117,189},{214,218,224,186,138,201},
    {166,179,166,161,163,191},{110,120,113, 84,108, 99},
    {166,179,166,161,163,191},{138,152,138,116,139,157},
    {173,110,135, 85,128, 46},{ 57, 68, 54, 41, 66,108},
    {128,153,128,117,125,122},{201,201,204,179,117,189},
    {166,179,166,161,163,191},{124,130,124,112,139, 96},
    {128,153,128,117,125,122},{173,110,135, 85,128, 46},
    { 57, 68, 54, 41, 66,108},{128,153,128,117,125,122},
    {138,152,138,116,139,157},{166,179,166,161,163,191},
    {181,186,194,135,130,186},{242,214,178,242,252,143},
    {128,153,128,117,125,122},{181,194,181,162,168,181},
    {201,201,204,179,117,189},{166,179,166,161,163,191},
    {122,130,120,112,141, 96},{166,179,166,161,163,191},
    {137,140,133,123,140,130},{128,153,128,117,125,122},
    {166,179,166,161,163,191},{110,120,113, 84,108, 99},
    {137,140,133,123,140,130},{ 25, 36, 25, 24, 25, 36},
};

/* ============================================================
 * 步态表 (Flash)
 * 0站 1爬 2慢走 3走 4快走 5小跑 6跑 7恢复 8过渡 9自适应 10下坡 11爬坡
 * ============================================================ */
const u8 code GAIT_MAP[64] = {
    6, 1, 8, 2, 2, 5, 7, 2, 2, 2, 3, 0, 3, 4, 0, 5,
    3, 9, 2, 2, 4, 3,10, 7, 4, 2, 2, 7, 7, 3, 2, 3,
    4, 6, 3, 2, 3, 5,11, 7, 2, 4, 3, 9, 2,11, 7, 2,
    5, 3, 6, 0, 2, 5, 4, 3, 9, 3, 8, 2, 3, 2, 8, 7,
};

const u8 code GAIT_PARAM[12][4] = {
    { 0, 0, 0,15},{ 5,15, 4,25},{12,30, 6,45},{20,40, 8,55},
    {30,50,10,70},{45,60,13,65},{70,80,15,90},{ 6,10, 3,40},
    {15,35, 5,50},{12,35, 5,50},{ 8,20, 4,35},{10,50, 5,50},
};

/* ============================================================
 * 运行时变量
 * ============================================================ */
u8  ylyw_hex;         /* 卦象 1-64 */
u8  ylyw_gait;        /* 步态 0-11 */
u16 ylyw_phase;       /* 步态相位 */
u8  ylyw_yao[6];      /* 六爻值 [0-255] */
u8  ylyw_state[6];    /* 六维状态 [0-255] */
u8  ylyw_last_hex;    /* 上一帧卦象 */
u16 ylyw_stable_cnt;  /* 稳定计数 */
s16 ylyw_last_roll;   /* 上一帧Roll偏差（用于计算变化率） */

/* 舵机中位 */
const u8 code SERVO_MID[24] = {
    128,128,128,128,128,128,128,128,
    128,128,128,128,128,128,128,128,
    128,128,128,128,128,128,128,128,
};

/* ============================================================
 * ADC → 六爻状态映射
 * ============================================================ */
void ylyw_read_sensors(void) {
    u8 i;
    s16 raw[3];
    s16 dev[3];
    u16 pitch_dev;
    u16 roll_dev;
    u16 tilt;
    u16 roll_rate;

    get_present_value();
    for (i=0; i<3; i++) {
        raw[i] = value_present[i];
        dev[i] = (s16)raw[i] - (s16)balance_value[i];
    }

    /* 初爻: 姿态稳定 */
    pitch_dev = (dev[2] > 0) ? (u16)dev[2] : (u16)(-dev[2]);
    roll_dev  = (dev[0] > 0) ? (u16)dev[0] : (u16)(-dev[0]);
    tilt = pitch_dev + roll_dev;

    if      (tilt < 10)  ylyw_state[0] = 240;
    else if (tilt < 20)  ylyw_state[0] = 200;
    else if (tilt < 40)  ylyw_state[0] = 150;
    else if (tilt < 80)  ylyw_state[0] = 100;
    else if (tilt < 160) ylyw_state[0] =  50;
    else                 ylyw_state[0] =  20;

    /* 二爻: 质心高度 */
    if      (tilt < 20) ylyw_state[1] = 220;
    else if (tilt < 60) ylyw_state[1] = 170;
    else                ylyw_state[1] = 120;

    /* 三爻: 力分布 */
    ylyw_state[2] = 180;

    /* 四爻: ZMP裕度 */
    if      (tilt < 10)  ylyw_state[3] = 240;
    else if (tilt < 30)  ylyw_state[3] = 180;
    else if (tilt < 60)  ylyw_state[3] = 120;
    else if (tilt < 120) ylyw_state[3] =  60;
    else                 ylyw_state[3] =  20;

    /* 五爻: 扰动（Roll变化率） */
    if (dev[0] > ylyw_last_roll)
        roll_rate = (u16)(dev[0] - ylyw_last_roll);
    else
        roll_rate = (u16)(ylyw_last_roll - dev[0]);
    ylyw_last_roll = dev[0];

    if      (roll_rate < 5)  ylyw_state[4] = 230;
    else if (roll_rate < 10) ylyw_state[4] = 180;
    else if (roll_rate < 20) ylyw_state[4] = 120;
    else if (roll_rate < 40) ylyw_state[4] =  60;
    else                     ylyw_state[4] =  20;

    /* 上爻: 地形 */
    ylyw_state[5] = 210;
}

/* ============================================================
 * 卦象匹配（整数余弦相似度）
 * ============================================================ */
u8 ylyw_match(const u8 yao[6]) {
    u8 i, j, best;
    u32 max_sim;
    u32 yao_n2;
    u32 dot;
    u32 tn2;
    u32 sim;

    best = 0;
    max_sim = 0;
    yao_n2 = 0;
    for (i=0; i<6; i++) yao_n2 += (u16)yao[i] * yao[i];

    for (i=0; i<64; i++) {
        dot = 0;
        tn2 = 0;
        for (j=0; j<6; j++) {
            dot += (u16)yao[j] * HEXAGRAM[i][j];
            tn2 += (u16)HEXAGRAM[i][j] * HEXAGRAM[i][j];
        }
        sim = (dot/10)*(dot/10) / ((yao_n2/10)*(tn2/10) + 1);
        if (sim > max_sim) { max_sim = sim; best = i; }
    }
    return best + 1;
}

/* ============================================================
 * 主推理
 * ============================================================ */
void ylyw_infer(const u8 state[6]) {
    u8 i;
    for (i=0; i<6; i++) ylyw_yao[i] = state[i];
    ylyw_last_hex = ylyw_hex;
    ylyw_hex = ylyw_match(ylyw_yao);
    ylyw_gait = GAIT_MAP[ylyw_hex - 1];
}

/* ============================================================
 * 步态→24舵机角度
 * ============================================================ */
void ylyw_servo_angles(u8 angles[24]) {
    u8 i;
    u8 spd, freq, force;
    u8 ph;
    s16 sv, cv;
    u8 ah, ak;
    s16 lh, lk;
    u8 bal;

    spd  = GAIT_PARAM[ylyw_gait][0];
    freq = GAIT_PARAM[ylyw_gait][2];
    force= GAIT_PARAM[ylyw_gait][3];

    for (i=0; i<24; i++) angles[i] = SERVO_MID[i];

    if (spd < 2) return;

    ylyw_phase += freq;
    ph = ylyw_phase >> 8;

    /* 三角波近似正弦 */
    if (ph & 0x80) {
        sv = (s16)(256 - (ph & 0x7F)*2 - 1);
        cv = (s16)(-(ph & 0x7F)*2);
    } else {
        sv = (s16)((ph & 0x7F)*2);
        cv = (s16)(256 - (ph & 0x7F)*2 - 1);
    }

    ah = (u8)((u16)spd * force / 100 * 3 / 5);
    ak = (u8)((u16)spd * force / 100 * 2 / 5);

    /* 左腿 */
    lh = ((s16)ah * sv) / 256;
    lk = (sv > 0) ? ((s16)ak * sv) / 256 : 0;
    angles[3] = (u8)(SERVO_MID[3] + lh);
    angles[5] = (u8)(SERVO_MID[5] + lh);
    angles[4] = (u8)(SERVO_MID[4] - lk);

    /* 右腿（反相） */
    angles[0] = (u8)(SERVO_MID[0] - lh);
    angles[2] = (u8)(SERVO_MID[2] - lh);
    lk = (cv > 0) ? ((s16)ak * cv) / 256 : 0;
    angles[1] = (u8)(SERVO_MID[1] - lk);

    /* 侧向平衡 */
    bal = spd / 3;
    angles[8]  = SERVO_MID[8]  + bal * 2;
    angles[9]  = SERVO_MID[9]  - bal * 2;
    angles[10] = SERVO_MID[10] - bal * 2;
    angles[11] = SERVO_MID[11] + bal * 2;
}

/* ============================================================
 * YLYW平衡修正（替代adc_adjust的硬阈值）
 * ============================================================ */
void ylyw_balance_check(void) {
    u8 i;
    s16 dev[3];
    u16 tilt;

    get_present_value();
    for (i=0; i<3; i++) dev[i] = (s16)value_present[i] - (s16)balance_value[i];

    if (ylyw_hex != ylyw_last_hex) {
        tilt = 0;
        if (dev[2] > 0) tilt += (u16)dev[2]; else tilt += (u16)(-dev[2]);
        if (dev[0] > 0) tilt += (u16)dev[0]; else tilt += (u16)(-dev[0]);

        if (tilt > 60) {
            ylyw_hex = 24;
            ylyw_gait = 7;
        } else if (tilt > 30) {
            ylyw_hex = 15;
            ylyw_gait = 0;
        }
    }
}

/* ============================================================
 * 初始化
 * ============================================================ */
void ylyw_init(void) {
    ylyw_phase = 0;
    ylyw_hex = 52;
    ylyw_last_hex = 52;
    ylyw_gait = 0;
    ylyw_stable_cnt = 0;
    ylyw_last_roll = 0;

    get_balance_value();
    delay500ms(1);

    ylyw_read_sensors();
    ylyw_infer(ylyw_state);
}

/* ============================================================
 * 单步: 传感器→推理→舵机→PWM (每20ms)
 * ============================================================ */
void ylyw_step(void) {
    u8 angles[24];
    u8 i;

    ylyw_read_sensors();
    ylyw_infer(ylyw_state);
    ylyw_balance_check();
    ylyw_servo_angles(angles);

    for (i=0; i<24; i++) position[i] = angles[i];
    PWM_24();
}

/* ============================================================
 * 主循环
 * ============================================================ */
void ylyw_main(void) {
    ylyw_step();
    low_level_500u(40);
}

/* ============================================================
 * 步态选择：手动注入期望步态（PS2/串口控制用）
 * ============================================================ */
void ylyw_set_demo_gait(u8 gait_id) {
    u8 i;
    if (gait_id == 0) {
        ylyw_state[0] = 230; ylyw_state[1] = 210;
        ylyw_state[2] = 195; ylyw_state[3] = 230;
        ylyw_state[4] =  13; ylyw_state[5] = 210;
    } else if (gait_id == 1) {
        ylyw_state[0] = 184; ylyw_state[1] = 186;
        ylyw_state[2] = 175; ylyw_state[3] = 166;
        ylyw_state[4] =  51; ylyw_state[5] = 205;
    } else if (gait_id == 2) {
        ylyw_state[0] = 166; ylyw_state[1] = 179;
        ylyw_state[2] = 166; ylyw_state[3] = 153;
        ylyw_state[4] =  77; ylyw_state[5] = 200;
    } else if (gait_id == 3) {
        ylyw_state[0] = 140; ylyw_state[1] = 190;
        ylyw_state[2] = 185; ylyw_state[3] = 128;
        ylyw_state[4] = 133; ylyw_state[5] = 195;
    } else if (gait_id == 4) {
        ylyw_state[0] = 120; ylyw_state[1] = 192;
        ylyw_state[2] = 200; ylyw_state[3] = 108;
        ylyw_state[4] = 158; ylyw_state[5] = 200;
    }
}

#endif /* __YLYW_8051_H__ */
