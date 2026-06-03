/**
 * YLYW UART命令解析 — 追加到main.c
 * 
 * 协议: 0xAA [24舵机角度] 0x55
 * 
 * 使用方法:
 *   1. 在main.c开头 #include "ylyw_8051.h"
 *   2. 在UART1_Interrupt()末尾调用 ylyw_uart_parse(SBUF)
 *   3. 在主循环中调用 ylyw_uart_process()
 */

/* ============ 追加变量（放在文件顶部全局区）============ */
unsigned char ylyw_uart_buf[26];  // 接收缓冲区
unsigned char ylyw_uart_idx = 0; // 接收索引
bit ylyw_frame_ready = 0;        // 帧就绪标志

/* ============ 追加到UART1_Interrupt()末尾 ============ */
void ylyw_uart_parse(unsigned char byte) 
{
    if (byte == 0xAA) {
        // 帧头
        ylyw_uart_idx = 0;
        return;
    }
    
    if (ylyw_uart_idx < 24) {
        // 接收24舵机角度
        ylyw_uart_buf[ylyw_uart_idx] = byte;
        ylyw_uart_idx++;
        return;
    }
    
    if (byte == 0x55 && ylyw_uart_idx == 24) {
        // 帧尾，数据完整
        ylyw_frame_ready = 1;
    }
    
    ylyw_uart_idx = 0;
}

/* ============ 在主循环while(1)中调用 ============ */
void ylyw_check_uart(void)
{
    if (ylyw_frame_ready) {
        ylyw_frame_ready = 0;
        
        // 将接收到的角度写入position[]
        unsigned char i;
        for (i = 0; i < 24; i++) {
            position[i] = ylyw_uart_buf[i];
        }
        
        // 输出PWM
        PWM_24();
    }
}


/* ============ 使用方法示例 ============ */
/*
// ---- 修改后的main()主循环 ----
void main(void) 
{
    // ... 原有初始化 ...
    Uart_Init();
    initial_position();
    
    while(1) 
    {
        // YLYW串口控制
        ylyw_check_uart();
        
        // 保留原有PS2/红外控制（可选）
        if (PS2_connected) {
            // 原有逻辑...
        }
    }
}

// ---- 修改后的UART1中断 ----
void UART1_Interrupt(void) interrupt UART1_VECTOR
{
    if(RI) {
        RI = 0;
        ylyw_uart_parse(SBUF);  // ← 加这一行
    }
}
*/
