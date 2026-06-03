/**
 * YLYW 8051独立运行 — 追加到main.c
 * 
 * 无需串口，YLYW推理在MCU上本地执行
 * 
 * 使用方法:
 *   1. #include "ylyw_8051.h"
 *   2. main()中调用 ylyw_init()
 *   3. 主循环中调用 ylyw_main_loop()
 */

#include "ylyw_8051.h"

/* 模拟传感器状态（步行时根据相位自动生成） */
unsigned char ylyw_state[6];    // 6维状态[0-255]
unsigned char ylyw_step_count;  // 步数计数器

/**
 * 从步态参数生成模拟传感器状态
 * 真实部署时替换为IMU/力传感器读数
 */
void ylyw_simulate_state(unsigned char gait_type, unsigned char phase) 
{
    unsigned char speed = GAIT_PARAMS[gait_type][0];
    
    if (speed == 0) {
        // 站立
        ylyw_state[0] = 230;  // posture
        ylyw_state[1] = 220;  // com_height
        ylyw_state[2] = 200;  // force_dist
        ylyw_state[3] = 235;  // zmp_margin
        ylyw_state[4] = 13;   // disturbance (低=稳定)
        ylyw_state[5] = 205;  // terrain
    } else if (speed < 30) {
        // 慢走
        ylyw_state[0] = 175;  ylyw_state[1] = 185;
        ylyw_state[2] = 170;  ylyw_state[3] = 155;
        ylyw_state[4] = 65;   ylyw_state[5] = 200;
    } else if (speed < 50) {
        // 快走/小跑
        ylyw_state[0] = 145;  ylyw_state[1] = 190;
        ylyw_state[2] = 180;  ylyw_state[3] = 125;
        ylyw_state[4] = 140;  ylyw_state[5] = 200;
    } else {
        // 奔跑
        ylyw_state[0] = 120;  ylyw_state[1] = 195;
        ylyw_state[2] = 195;  ylyw_state[3] = 105;
        ylyw_state[4] = 165;  ylyw_state[5] = 200;
    }
}

/**
 * 备选：通过UART接收外部状态向量
 * 协议: 0xBB [6状态字节] 0x55
 */
bit ylyw_ext_state_ready = 0;
unsigned char ylyw_ext_state[6];

/**
 * 主循环：YLYW推理 → 舵机输出
 * 每20ms调用一次（50Hz控制频率）
 */
void ylyw_main_loop(void) 
{
    unsigned char servo_angles[24];
    
    // 选择状态来源：
    // 方式A: 内部模拟（独立运行）
    ylyw_simulate_state(ylyw_gait, ylyw_step_phase);
    
    // 方式B: 外部串口注入（取消下面注释）
    // if (ylyw_ext_state_ready) {
    //     ylyw_ext_state_ready = 0;
    //     ylyw_infer(ylyw_ext_state);
    //     ylyw_gait = GAIT_TABLE[ylyw_hexagram - 1];
    // }
    
    // YLYW推理 + 生成舵机角度
    ylyw_step(ylyw_state, servo_angles);
    
    // 写入position[]
    unsigned char i;
    for (i = 0; i < 24; i++) {
        position[i] = servo_angles[i];
    }
    
    // 输出PWM
    PWM_24();
    
    // 20ms延时
    low_level_500u(40);
}


/* ============ 集成到main() ============ */
/*
#include "ylyw_8051.h"

void main(void) 
{
    // ... 原有初始化(Uart_Init, initial_position等) ...
    
    ylyw_init();
    
    while(1) 
    {
        ylyw_main_loop();
    }
}
*/
