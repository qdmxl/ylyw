//#############################################################################
//头文件包含
//#############################################################################
//#include <math.h>
#include "REG15W4Kxx.h"
#include "delay.h"
#include "main.h"
#include "basal.h"
#include "tuxinghua.h"
#include "HT1621.h"

//#############################################################################
//变量定义
//#############################################################################
unsigned int  balance_value[3]={0};         //存储平衡时的各通道值
unsigned int  value_present[3]={0};         //存储各通道当前值
unsigned char channel_present=0;            //描述当前通道
unsigned char channel_total=3;              //总通道数
unsigned char balance_sample_num=50;        //获取平衡值的采样次数
unsigned char balance_sample_num_buf=50;
unsigned char flag_balance=0;               //平衡值采样结束标志
unsigned char flag_adc_complete=1;          //adc采样结束中断
unsigned char flag_adjust = 0; 
unsigned char flag_jump   = 0;  

//#############################################################################
//函数名称：void initial_adc(void)
//函数说明：adc初始化
//入口参数：无
//出口参数：无	  
//#############################################################################
void initial_adc(void)
{
	P1ASF = 0x07;         //将P1.0-P1.1口作为模拟输入	
	CLK_DIV  |= 0x20;     //高两位在ADC_RES, 低8位在ADC_RESL
	ADC_RES   = 0;	
	ADC_RESL  = 0;
	ADC_CONTR = 0xE0;     //ADC电源打开，速度设为最快
	EADC = 1;             //ADC中断使能位  1-->使能 0-->关闭
}

//#############################################################################
//函数名称：void start_adc(void)
//函数说明：启动adc
//入口参数：无
//出口参数：无
//#############################################################################
void start_adc(void)
{
	ADC_CONTR =  0xE0 + channel_present;  //启动某一通道的adc
	ADC_CONTR |= 0x08;                    //ADC_START=1
}

//#############################################################################
//函数名称：void get_balance_value(void)
//函数说明：获得平衡状态的值
//入口参数：无
//出口参数：无
//#############################################################################
void get_balance_value(void)
{
  unsigned char i;
	for(i=0;i<channel_total*balance_sample_num;i++)
	{
	    start_adc();
		while(flag_adc_complete);
		flag_adc_complete=1;
	}
	flag_adjust=1;
}						
//#############################################################################
//函数名称：void get_present_value(void)
//函数说明：获得当前状态的值
//入口参数：无
//出口参数：无
//#############################################################################
void get_present_value(void)
{
  unsigned char i;
	for(i=0;i<channel_total;i++)
	{
	  start_adc();
		while(flag_adc_complete);
		flag_adc_complete=1;
	}
}

//#############################################################################
//函数名称：void adc_int(void) interrupt 5
//函数说明：adc中断
//入口参数：无
//出口参数：无
//#############################################################################
void adc_int(void) interrupt 5    
{
  unsigned int buf=0;
	unsigned char i;

  ADC_CONTR &= 0xef;      //ADC_flag=0

	if(flag_balance == 0)
	{
	    buf=ADC_RES;
	    buf<<=8;
	    buf+=ADC_RESL;											 

	    balance_value[channel_present]+=buf;
		channel_present++;
		if(channel_present==channel_total)
		{
	        channel_present=0;
			balance_sample_num_buf--;
		}
		if(balance_sample_num_buf==0)
		{
		    for(i=0;i<channel_total;i++)
		       balance_value[i]=balance_value[i]/balance_sample_num;
	    	flag_balance=1;
		}
	}
	else
	{
	    buf=ADC_RES;
	    buf<<=8;
	    buf+=ADC_RESL;
	    value_present[channel_present]=buf;
		channel_present++;
		if(channel_present==channel_total)
	        channel_present=0;
	}
	flag_adc_complete=0;
}  

//#############################################################################
//函数名称：void adc_adjust(void)
//函数说明：adc调整
//入口参数：无
//出口参数：无
//#############################################################################
void adc_adjust(void)
{  
	uchar i;
 	flag_adjust = 0;
	get_present_value();

	// 右倾
	if((value_present[2]>balance_value[2]+40)&&(value_present[1]<balance_value[1]-40))		  
	{   
		EX0 = 0;
		TR1 = 0;
		
		delay500us(50);
		position[7]+=40;
					PWM_24();
		delay500ms(1);
		position[7]-=40;
					PWM_24();
		delay500ms(1); 
		flag_jump=1;
		flag_adjust=1;
		PWM_24();
		
		for(i=0;i<24;i++)
		{
			 jichu[i]=0;
		}		
		EX0  = 1;
		B_IR_Press = 0;		//清除IR键按下标志   
	}

	//左倾
	if((value_present[2]<balance_value[2]-40)&&(value_present[1]<balance_value[1]-40))
	{
		EX0 = 0;
		TR1 = 0;
		
		delay500us(50);
		position[6]-=40;
		PWM_24();
		delay500ms(1);
		position[6]+=40;
		PWM_24();
		delay500ms(1);	
		flag_jump=1;
		flag_adjust=1;
		PWM_24();
		
		for(i=0;i<24;i++)
		{
			jichu[i]=0;
		}  
		EX0  = 1;
		B_IR_Press = 0;		//清除IR键按下标
	}

	//后倾
	if((value_present[0]<balance_value[0]-40)&&(value_present[1]<balance_value[1]-40))
	{	  
		EX0 = 0;
		TR1 = 0;
		
		delay500us(50);
		hpq();
		delay500us(100);
		flag_jump=1;
		flag_adjust=1;
		PWM_24();
		
		for(i=0;i<24;i++)
		{
			jichu[i]=0;
		}   
		EX0  = 1;
		B_IR_Press = 0;		//清除IR键按下标      
	}

	//前倾
	if((value_present[0]>balance_value[0]+40)&&(value_present[1]<balance_value[1]-40))
	{	  
		EX0 = 0;
		TR1 = 0;
		
		delay500us(50);
		qianpq();
		delay500us(100);
		flag_jump=1;
		flag_adjust=1;
		PWM_24();
		
		for(i=0;i<24;i++)
		{
			jichu[i]=0;
		}   
		EX0  = 1;
		B_IR_Press = 0;		//清除IR键按下标 
	}
		 
	flag_adjust = 1;
}  









