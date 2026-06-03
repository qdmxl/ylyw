#ifndef _qianshou_
#define _qianshou_

extern unsigned char change;     //红外线接收队列
extern unsigned char total;      //千手总数
extern unsigned char part;   	   //千手单台数
//extern unsigned char t1bit;		   //定时器0千手延时标志位

//extern void low_level_t1(unsigned short int THTL );

extern void ForwardDelay(void);
extern void BackDelay(void);
extern void qianshou(void);
//extern void time1_init(void);

#endif