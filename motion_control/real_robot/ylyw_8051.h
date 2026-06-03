/**
 * YLYW 运动控制推理 — 8051定点版
 * 适配STC15W4K32S4，约2KB代码
 * 
 * 数据流: 传感器状态 → L1八卦隶属度 → L2六爻编码 → L3卦象匹配 → 24舵机角度
 * 
 * 使用方法:
 *   1. 将本文件加入Keil工程
 *   2. main()中调用 ylyw_init() 初始化模板
 *   3. 循环调用 ylyw_step() 每步输出舵机角度
 */
#include "basal.h"
#include "REG15W4Kxx.h"

/* ================================================================
 * 一、数据类型定义（8051定点运算，比例因子256）
 * ================================================================ */
typedef signed short fix16;   // 定点数: 实际值 = fix16 / 256
#define FIX_ONE   256
#define FIX_HALF  128
#define FIX(x)    ((fix16)((x) * FIX_ONE))

/* ================================================================
 * 二、L1 八卦隶属度（8个卦 × 6维原型，定点存储）
 * ================================================================ */
// 八卦原型: 乾/坤/震/艮/离/坎/兑/巽，每卦6维 (8×6=48字节)
const char code TRIGRAM_PROTOTYPES[8][6] = {
    /* 乾 */ {FIX(0.85), FIX(0.80), FIX(0.90), FIX(0.80), FIX(0.15), FIX(0.70)},
    /* 坤 */ {FIX(0.70), FIX(0.40), FIX(0.30), FIX(0.60), FIX(0.40), FIX(0.50)},
    /* 震 */ {FIX(0.30), FIX(0.55), FIX(0.55), FIX(0.25), FIX(0.85), FIX(0.60)},
    /* 艮 */ {FIX(0.95), FIX(0.65), FIX(0.75), FIX(0.95), FIX(0.05), FIX(0.50)},
    /* 离 */ {FIX(0.55), FIX(0.60), FIX(0.50), FIX(0.50), FIX(0.40), FIX(0.90)},
    /* 坎 */ {FIX(0.25), FIX(0.35), FIX(0.40), FIX(0.20), FIX(0.70), FIX(0.40)},
    /* 兑 */ {FIX(0.65), FIX(0.70), FIX(0.60), FIX(0.65), FIX(0.30), FIX(0.55)},
    /* 巽 */ {FIX(0.50), FIX(0.50), FIX(0.45), FIX(0.50), FIX(0.45), FIX(0.55)},
};

// 八卦名称
const char code *TRIGRAM_NAMES[8] = {"乾","坤","震","艮","离","坎","兑","巽"};

/* ================================================================
 * 三、L3 六十四卦爻模板（64卦 × 6爻，定点存储，384字节）
 * ================================================================ */
// 每卦6爻，值范围[0,255]（归一化0-1 × 255）
const unsigned char code HEXAGRAM_TEMPLATES[64][6] = {
    /* 01 乾 */ {242,240,235,229,153,210},
    /* 02 坤 */ { 31, 51, 38, 69, 64,109},
    /* 03 屯 */ {140,153,128,117,140,130},
    /* 04 蒙 */ { 72, 79, 73, 55, 71, 64},
    /* 05 需 */ { 73, 80, 70, 54, 71, 64},
    /* 06 讼 */ {135,152,138,116,139,157},
    /* 07 师 */ { 58, 79, 62, 48, 87, 52},
    /* 08 比 */ {128,153,128,117,125,122},
    /* 09 小畜*/ { 71, 80, 71, 55, 72, 65},
    /* 10 履 */ { 71, 80, 70, 55, 72, 65},
    /* 11 泰 */ {166,179,166,161,163,191},
    /* 12 否 */ {235,210,166,237,247,143},
    /* 13 同人*/ {166,179,166,161,163,191},
    /* 14 大有*/ {201,201,204,179,117,189},
    /* 15 谦 */ {242,214,178,242,252,143},
    /* 16 豫 */ {191,204,201,163,173,191},
    /* 17 随 */ {166,179,166,161,163,191},
    /* 18 蛊 */ { 81, 86, 78, 73, 91, 63},
    /* 19 临 */ {128,153,128,117,125,122},
    /* 20 观 */ { 73, 79, 71, 55, 72, 66},
    /* 21 噬嗑*/ {201,201,204,179,117,189},
    /* 22 贲 */ {166,179,166,161,163,191},
    /* 23 剥 */ { 81, 57, 74, 58, 93, 49},
    /* 24 复 */ { 57, 68, 54, 41, 66,108},
    /* 25 无妄*/ {201,201,204,179,117,189},
    /* 26 大畜*/ {128,153,128,117,125,122},
    /* 27 颐 */ { 72, 79, 73, 55, 71, 64},
    /* 28 大过*/ { 57, 68, 54, 41, 66,108},
    /* 29 坎 */ { 49, 63, 51, 40, 51,108},
    /* 30 离 */ {166,179,166,161,163,191},
    /* 31 咸 */ {128,153,128,117,125,122},
    /* 32 恒 */ {166,179,166,161,163,191},
    /* 33 遁 */ {201,201,204,179,117,189},
    /* 34 大壮*/ {212,218,224,187,138,201},
    /* 35 晋 */ {166,179,166,161,163,191},
    /* 36 明夷*/ { 72, 79, 73, 55, 71, 64},
    /* 37 家人*/ {166,179,166,161,163,191},
    /* 38 睽 */ {138,152,138,116,139,157},
    /* 39 蹇 */ {173,110,135, 85,128, 46},
    /* 40 解 */ { 57, 68, 54, 41, 66,108},
    /* 41 损 */ {128,153,128,117,125,122},
    /* 42 益 */ {201,201,204,179,117,189},
    /* 43 夬 */ {166,179,166,161,163,191},
    /* 44 姤 */ { 82, 87, 79, 74, 93, 64},
    /* 45 萃 */ {128,153,128,117,125,122},
    /* 46 升 */ {173,110,135, 85,128, 46},
    /* 47 困 */ { 57, 68, 54, 41, 66,108},
    /* 48 井 */ {128,153,128,117,125,122},
    /* 49 革 */ {138,152,138,116,139,157},
    /* 50 鼎 */ {166,179,166,161,163,191},
    /* 51 震 */ {181,186,194,135,130,186},
    /* 52 艮 */ {242,214,178,242,252,143},
    /* 53 渐 */ {128,153,128,117,125,122},
    /* 54 归妹*/ {181,194,181,162,168,181},
    /* 55 丰 */ {201,201,204,179,117,189},
    /* 56 旅 */ {166,179,166,161,163,191},
    /* 57 巽 */ { 81, 87, 79, 74, 94, 63},
    /* 58 兑 */ {166,179,166,161,163,191},
    /* 59 涣 */ {137,140,133,123,140,130},
    /* 60 节 */ {128,153,128,117,125,122},
    /* 61 中孚*/ {166,179,166,161,163,191},
    /* 62 小过*/ { 72, 79, 73, 55, 71, 64},
    /* 63 既济*/ {137,140,133,123,140,130},
    /* 64 未济*/ { 25, 36, 25, 24, 25, 36},
};

/* ================================================================
 * 四、64卦步态参数表（速度/步高/频率/力系数，定点）
 * ================================================================ */
// 速度等级映射: 0=站 1=爬 2=慢走 3=走 4=快走 5=小跑 6=跑 7=恢复
const unsigned char code GAIT_TABLE[64] = {
    /*01*/6, /*02*/1, /*03*/8, /*04*/2, /*05*/2, /*06*/5, /*07*/7, /*08*/2,
    /*09*/2, /*10*/2, /*11*/3, /*12*/0, /*13*/3, /*14*/4, /*15*/0, /*16*/5,
    /*17*/3, /*18*/9, /*19*/2, /*20*/2, /*21*/4, /*22*/3, /*23*/10,/*24*/7,
    /*25*/4, /*26*/2, /*27*/2, /*28*/7, /*29*/7, /*30*/3,
    /*31*/2, /*32*/3, /*33*/4, /*34*/6, /*35*/3, /*36*/2, /*37*/3, /*38*/5,
    /*39*/11,/*40*/7, /*41*/2, /*42*/4, /*43*/3, /*44*/9, /*45*/2, /*46*/11,
    /*47*/7, /*48*/2, /*49*/5, /*50*/3, /*51*/6, /*52*/0, /*53*/2, /*54*/5,
    /*55*/4, /*56*/3, /*57*/9, /*58*/3, /*59*/8, /*60*/2, /*61*/3, /*62*/2,
    /*63*/8, /*64*/7,
};
// 8=过渡 9=自适应 10=下坡 11=爬坡

// 步态参数: speed(cm/s), step_height(mm), freq(*10Hz), force(%)
const unsigned char code GAIT_PARAMS[12][4] = {
    /* 0 stand        */ {  0,  0,  0, 15},
    /* 1 crawl        */ {  5, 15,  8, 25},
    /* 2 slow_walk    */ { 12, 30, 12, 45},
    /* 3 walk         */ { 20, 40, 16, 55},
    /* 4 fast_walk    */ { 30, 50, 20, 70},
    /* 5 trot         */ { 45, 60, 25, 65},
    /* 6 run          */ { 70, 80, 30, 90},
    /* 7 recovery     */ {  6, 10,  5, 40},
    /* 8 transition   */ { 15, 35, 10, 50},
    /* 9 adaptive     */ { 12, 35, 10, 50},
    /*10 descend      */ {  8, 20,  8, 35},
    /*11 climb        */ { 10, 50, 10, 50},
};

/* ================================================================
 * 五、运行时变量
 * ================================================================ */
unsigned char ylyw_hexagram;    // 当前卦象编号(1-64)
unsigned char ylyw_gait;        // 当前步态类型(0-11)
fix16 ylyw_step_phase;          // 步态相位
unsigned char ylyw_yao[6];      // 六爻值[0-255]

/* ================================================================
 * 六、推理函数
 * ================================================================ */

// 定点乘法(a*b)>>8
fix16 fix_mul(fix16 a, fix16 b) {
    signed long t = (signed long)a * b;
    return (fix16)(t >> 8);
}

// 定点平方根近似（牛顿法）
fix16 fix_sqrt(fix16 x) {
    fix16 r = x;
    unsigned char i;
    if (x <= 0) return 0;
    for (i = 0; i < 5; i++) {
        if (r == 0) break;
        r = (r + (x * FIX_ONE) / r) >> 1;
    }
    return r;
}

/**
 * L1: 计算8维八卦隶属度
 * state[6]: 归一化状态[0-255]
 * 返回主导卦象索引(0-7)
 */
unsigned char ylyw_l1_trigram(const unsigned char state[6], fix16 *membership) {
    unsigned char i, j;
    fix16 max_mu = 0;
    unsigned char dominant = 0;
    
    for (i = 0; i < 8; i++) {
        fix16 sum = 0;
        for (j = 0; j < 6; j++) {
            fix16 diff = (fix16)state[j] - (fix16)TRIGRAM_PROTOTYPES[i][j];
            if (diff < 0) diff = -diff;
            // 高斯核: max(0, 1 - |diff| * 1.5)
            fix16 penalty = (diff * 3) >> 1;  // diff * 1.5
            fix16 term = FIX_ONE - penalty;
            if (term < 0) term = 0;
            sum += term;
        }
        membership[i] = sum / 6;
        if (membership[i] > max_mu) {
            max_mu = membership[i];
            dominant = i;
        }
    }
    return dominant;
}

/**
 * L2: 六爻编码
 * 将6维状态直接映射为爻值(≥128为阳爻)
 */
void ylyw_l2_encoder(const unsigned char state[6], unsigned char yao[6]) {
    unsigned char i;
    for (i = 0; i < 6; i++) {
        yao[i] = state[i];
    }
}

/**
 * L3: 卦象匹配 → 余弦相似度
 * 返回最佳卦象编号(1-64)
 */
unsigned char ylyw_l3_match(const unsigned char yao[6]) {
    unsigned char i, j;
    unsigned long max_sim = 0;
    unsigned char best = 1;
    
    // 计算yao向量的模平方
    unsigned long yao_norm2 = 0;
    for (i = 0; i < 6; i++) {
        yao_norm2 += (unsigned int)yao[i] * yao[i];
    }
    
    for (i = 0; i < 64; i++) {
        unsigned long dot = 0;
        unsigned long t_norm2 = 0;
        for (j = 0; j < 6; j++) {
            dot += (unsigned int)yao[j] * HEXAGRAM_TEMPLATES[i][j];
            t_norm2 += (unsigned int)HEXAGRAM_TEMPLATES[i][j] * HEXAGRAM_TEMPLATES[i][j];
        }
        // 相似度 = dot / sqrt(norm2_yao * norm2_template)
        // 直接用dot²/(norm2_yao * norm2_template)比较
        unsigned long sim_num = dot * dot;
        unsigned long sim_den = yao_norm2 * t_norm2;
        if (sim_den == 0) sim_den = 1;
        if (sim_num > max_sim) {
            max_sim = sim_num;
            best = i + 1;
        }
    }
    return best;
}

/**
 * L3+: 爻位关系分析 → 步态修正
 * 简化版：检查初爻(稳定性)和五爻(扰动)
 */
unsigned char ylyw_l3_relations(const unsigned char yao[6]) {
    unsigned char quality = 5;  // 0-10, 5为正常
    // 初爻<64 → 不稳定，降力
    if (yao[0] < 64) quality -= 2;
    // 五爻<96 → 有扰动
    if (yao[4] < 96) quality -= 1;
    // 四爻<64 → 危险
    if (yao[3] < 64) quality -= 2;
    return quality;
}

/**
 * 完整推理: state[6] → hexagram → gait → servo angles
 */
void ylyw_infer(const unsigned char state[6]) {
    fix16 membership[8];
    unsigned char trigram;
    
    // L1
    trigram = ylyw_l1_trigram(state, membership);
    // L2
    ylyw_l2_encoder(state, ylyw_yao);
    // L3
    ylyw_hexagram = ylyw_l3_match(ylyw_yao);
    // L3+
    ylyw_l3_relations(ylyw_yao);
    // 获取步态类型
    ylyw_gait = GAIT_TABLE[ylyw_hexagram - 1];
}

/**
 * 获取当前步态的24舵机目标角度
 * 根据步态类型和相位生成舵机角度序列
 */
void ylyw_get_servo_angles(unsigned char angles[24]) {
    unsigned char i;
    unsigned char speed  = GAIT_PARAMS[ylyw_gait][0];
    unsigned char height = GAIT_PARAMS[ylyw_gait][1];
    unsigned char freq   = GAIT_PARAMS[ylyw_gait][2];
    unsigned char force  = GAIT_PARAMS[ylyw_gait][3];
    
    // 初始位置（从basal.c的initial_position）
    const unsigned char INIT[24] = {
        128, 128, 128, 128, 128, 128, 128, 128,
        128, 128, 128, 128, 128, 128, 128, 128,
        128, 128, 128, 128, 128, 128, 128, 128,
    };
    
    // 更新相位
    ylyw_step_phase += freq;
    
    if (speed == 0) {
        // 站立：保持初始位置
        for (i = 0; i < 24; i++) angles[i] = INIT[i];
        return;
    }
    
    // 行走：正弦步态生成
    // 使用8051内置sin近似（查表或泰勒）
    signed char phase = ylyw_step_phase;
    signed char sin_val, cos_val;
    // 简化：用三角形波近似正弦
    sin_val = (phase & 0x80) ? (signed char)(256 - (phase & 0x7F)*2) : (signed char)((phase & 0x7F)*2);
    cos_val = (phase & 0x80) ? (signed char)(-(phase & 0x7F)*2) : (signed char)(256 - (phase & 0x7F)*2);
    
    // 右腿(0-5): 髋前后[0,2] + 膝[1]
    unsigned char hip_amp = speed;
    unsigned char knee_amp = speed * 2 / 3;
    
    // 左腿摆动
    angles[3] = INIT[3] + ((signed short)hip_amp * sin_val) / 256;
    angles[5] = INIT[5] + ((signed short)hip_amp * sin_val) / 256;
    angles[4] = INIT[4] - ((signed short)knee_amp * (sin_val > 0 ? sin_val : 0)) / 256;
    
    // 右腿摆动（相反相位）
    angles[0] = INIT[0] - ((signed short)hip_amp * sin_val) / 256;
    angles[2] = INIT[2] - ((signed short)hip_amp * sin_val) / 256;
    angles[1] = INIT[1] + ((signed short)knee_amp * (cos_val > 0 ? cos_val : 0)) / 256;
    
    // 侧向平衡(8-11): 根据速度微调
    angles[8]  = INIT[8]  + speed / 4;
    angles[9]  = INIT[9]  - speed / 4;
    angles[10] = INIT[10] - speed / 4;
    angles[11] = INIT[11] + speed / 4;
    
    // 上半身保持
    for (i = 12; i < 24; i++) {
        angles[i] = INIT[i];
    }
}

/* ================================================================
 * 七、初始化与主循环接口
 * ================================================================ */
void ylyw_init(void) {
    ylyw_step_phase = 0;
    ylyw_hexagram = 15;  // 谦卦→静止站立
    ylyw_gait = 0;       // stand
}

/**
 * ylyw_step: 每步调用，输出24舵机角度
 * state[6]: 6维归一化状态（可从传感器或内部模型获取）
 *   [0]姿态稳定 [1]质心高度 [2]力分布 [3]ZMP裕度 [4]扰动 [5]地形
 */
void ylyw_step(const unsigned char state[6], unsigned char servo_angles[24]) {
    ylyw_infer(state);
    ylyw_get_servo_angles(servo_angles);
}
