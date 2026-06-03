#ifndef __INFRARED_H
#define __INFRARED_H	

//红外线接收处理    红外线一共是4个字节的数据:包括，地址、地址的重复、数据、和数据的按位取反
//变量定义：												 
char     inf_array[2]      = {0};     //红外线接收队列
char     inf_dizhi         = 0;     //确认最新数据
char     inf_dizhichou     = 0;
char     inf_shuju         = 0;
char     inf_shujuf        = 0;
char     inf_dizhi_buf     = 0;     //缓冲区数据，有可能随时变化，不可相信
char     inf_dizhichou_buf = 0;
char     inf_shuju_buf     = 0;
char     inf_shujuf_buf    = 0;

char     inf_shunxu        = 0;     //输入次序，记录目前红外线接收的次序。
int      inf_zanshi        = 0;     //红外线数据暂时存储，在使用前应注意其值
char     inf_zanshi1       = 0;     //另一个暂时数据，用来做校验
char bdata  inf_mode       = 0;     //红外线状态及控制变量，按位使用
sbit     inf_mode_en       = inf_mode^7;
sbit     inf_mode_new      = inf_mode^6;
sbit     inf_mode_cuowu    = inf_mode^0;
sbit     P3_2              = P3^2;
//sbit     P3_4              = P3^4;

#define  kaishizhi_l       70       //此值为引导码最低阈值			  	根据晶振不同而不同，晶振越大此组值越大
#define  kaishizhi_h       230      //此值为引导码最高阈值
#define  inf_lingzhi_l     0x07     //此值为"0"码最低阈值
#define  inf_lingzhi_h     0x17     //此值为"0"码最高阈值
#define  inf_yizhi_l       0x18     //此值为"1"码最低阈值
#define  inf_yizhi_h       0x27     //此值为"1"码最高阈值
#define  inf_code_0        0x0F
#define  inf_code_1        0x0E
#define  inf_code_2        0x99     
#define  inf_code_3        0x01
#define  inf_code_4        0x02
#define  inf_code_5        0x03
#define  inf_code_6        0x04
#define  inf_code_7        0x05
#define  inf_code_8        0x06
#define  inf_code_9        0x07
#define  inf_code_10       0x08
#define  inf_code_11       0x09
#define  inf_code_12       0x0A
#define  inf_code_13       0x00
#define  inf_code_14       0x24
#define  inf_code_15       0x20
#define  inf_code_16       0x1E
#define  inf_code_17       0x18
#define  inf_code_18       0x1A
#define  inf_code_19       0x16
#define  inf_code_20       0x0B
#define  inf_code_21       0x12
#define  inf_code_22       0x10
#define  inf_code_23       0x11
#define  inf_code_24       0x0C
#define  inf_code_25       0x28
#define  inf_code_26       0x17
#define  inf_code_27       0x13

//#############################################################################
// 函数名称：void init_inf()
// 功    能：红外遥控初始化子程序
// 入口参数：无
// 出口参数：无
//#############################################################################
void init_inf(void)
{
    inf_array[0]=0xFF;
    inf_array[1]=0xFF;

    inf_dizhi_buf     = 0;
    inf_dizhichou_buf = 0;
    inf_shuju_buf     = 0;
    inf_shujuf_buf    = 0;

    inf_dizhi         = 0;
    inf_dizhichou     = 0;
    inf_shuju         = 0;
    inf_shujuf        = 0;

    inf_shunxu        = 0;
    inf_mode_en       = 1;      //开红外线接收软件模块
    inf_mode_cuowu    = 0;      //清除错误
    /*我们需要使用两部分的硬件资源，
    一是定时器1，
    二是外部中断0，
    下面是分别的初始化：*/
    P3_2 = 1;
 //   P3_4 = 1;
    //初始化定时器1：
    TMOD  = TMOD & 0x0F;        //初始化定时器1的计数方式为方式1
    TMOD  = TMOD | 0x10;

    TH1   = 0x0F;               //0x1F定时器高位
    TL1   = 0xFF;               //0xFF定时器低位

    TR1   = 0;                  //关定时器1计数
    IE    = IE | 0x88;          //总中断和定时器1要打开

    //初始化外部中断1：
    IT0   = 1;                  //INT0的处罚方式为下降沿触发
    IE    = IE | 0x81;          //总中断和外部中断0要打开	
}
//#############################################################################
// 函数名称：void T_1(void) interrupt 3
// 功    能：定时器1中断服务程序
// 入口参数：无
// 出口参数：无
//#############################################################################

void T_1(void) interrupt 3      //参与红外线接收
{
    TR1 = 0;
    inf_shunxu = 0;	
}
//#############################################################################
// 函数名称：void inf_gonggong()
// 功    能：红外线接收子程序
// 入口参数：无
// 出口参数：无
//#############################################################################

void inf_gonggong(void)         //红外线接收公共程序
{
    TR1   = 0;                  //定时器1停止计数，晶振是24M
    inf_zanshi =  TH1*256;      //读入定时器的值
    inf_zanshi += TL1;
    inf_zanshi -= 0x1FFF;
    inf_zanshi = inf_zanshi/128;    //处理计数值，做128分频

    TH1   = 0x0F;               //0x1F定时器高位
    TL1   = 0xFF;               //0xFF定时器低位
    TR1   = 1;                  //定时器1开始计数，由于晶振是24M
    inf_shunxu++;
}
//#############################################################################
// 函数名称：void inf_gongcuowu()
// 功    能：红外线错误子程序
// 入口参数：无
// 出口参数：无
//#############################################################################

void inf_gongcuowu(void)
{
    inf_mode_cuowu = 1;         //红外线接收出现错误
    inf_shunxu = 0;				     
}
//#############################################################################
// 函数名称：void inf_wancheng()
// 功    能：红外线完成子程序
// 入口参数：无
// 出口参数：无
//#############################################################################

void inf_wancheng(void)
{		 
    char jiaoyanzhi = 0xFF;
				
    TR1 = 0;
    inf_shunxu=0;
				 
    if(inf_dizhi_buf == inf_dizhichou_buf)  //校验数据，先地址再数据
    {	 
        inf_zanshi1 =  inf_shuju_buf;
        inf_zanshi1 |= inf_shujuf_buf;
        if(jiaoyanzhi == inf_zanshi1)       //如果为真则说明接收数据是正确的
        {	  
            
            inf_dizhi = inf_dizhi_buf;
            inf_dizhichou = inf_dizhichou_buf;
            inf_shuju = inf_shuju_buf;
            inf_shujuf = inf_shujuf_buf;
		
            if(inf_shuju == inf_code_0)     //这个码是清除设定码
                     {inf_array[1] = 0xFF;
				}
            if(inf_array[1] == jiaoyanzhi)  //如果等于FFH说明现在机器人的动作是空闲
            {	
				switch(inf_shuju)
                {
                case inf_code_0:  inf_array[1]=30;
                                  break;
                case inf_code_1:  inf_array[1]=1;
                                  break;
                case inf_code_2:  inf_array[1]=2;
                                  break;
                case inf_code_3:  inf_array[1]=3;
                                  break;
                case inf_code_4:  inf_array[1]=4;
                                  break;
                case inf_code_5:  inf_array[1]=5;
                                  break;
                case inf_code_6:  inf_array[1]=6;
                                  break;
                case inf_code_7:  inf_array[1]=7;
                                  break;
                case inf_code_8:  inf_array[1]=8;
                                  break;
                case inf_code_9:  inf_array[1]=9;
                                  break;
                case inf_code_10: inf_array[1]=10;
                                  break;
                case inf_code_11: inf_array[1]=11;
                                  break;
                case inf_code_12: inf_array[1]=12;
                                  break;
                case inf_code_13: inf_array[1]=13;
                                  break;
                case inf_code_14: inf_array[1]=14;
                                  break;
                case inf_code_15: inf_array[1]=15;
                                  break;
                case inf_code_16: inf_array[1]=16;
                                  break;
                case inf_code_17: inf_array[1]=17;
                                  break;
                case inf_code_18: inf_array[1]=18;
                                  break;
                case inf_code_19: inf_array[1]=19;
                                  break;
                case inf_code_20: inf_array[1]=20;
                                  break;
                case inf_code_21: inf_array[1]=21;
                                  break;
                case inf_code_22: inf_array[1]=22;
                                  break;
                case inf_code_23: inf_array[1]=23;
                                  break;
                case inf_code_24: inf_array[1]=24;
                                  break;
                case inf_code_25: inf_array[1]=25;
                                  break;
                case inf_code_26: inf_array[1]=26;
                                  break;
                case inf_code_27: inf_array[1]=27;
                                  break;
                default:          inf_array[1]=0xFF;
                                  break; 								
                }	    
            }
        }
    }
   
}
//#############################################################################
// 函数名称：void INT_0(void) interrupt 0()
// 功    能：外部中断0服务程序
// 入口参数：无
// 出口参数：无
//#############################################################################
void INT_0(void) interrupt 0
{  
    if(inf_mode_en == 1)       //如果红外线接收总控制开，那么才可以判断下面的所有
    { 
	   if(inf_shunxu == 0)
           { 
            TH1   = 0x0F;     //0x1F定时器高位
            TL1   = 0xFF;     //0xFF定时器低位
            TR1   = 1;        //定时器1开始计数，由于晶振是24M
            inf_shunxu++;     //顺序加一
            ET1   = 1;        //开定时器1的溢出中断使能			
           }
       else if(inf_shunxu == 1)
          {    inf_gonggong();   //红外线接收公共程序
					 
                if(inf_zanshi>kaishizhi_l)
                 {		 
         		    inf_dizhi_buf=0;
               		inf_dizhichou_buf=0;
               		inf_shuju_buf=0;
               		inf_shujuf_buf=0;
                 }
                else   inf_gongcuowu();                //公共错误处理 错误位置1，接收顺序清0
          }
       else
       {
            switch(inf_shunxu)
            {	 
        case 2:  inf_gonggong();			             //红外线接收公共程序
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_dizhi_buf&=0xFE;}              //清除最低位
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_dizhi_buf|=0x01;}              //置最低位
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 3:  inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_dizhi_buf&=0xFD;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_dizhi_buf|=0x02;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 4:  inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_dizhi_buf&=0xFB;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_dizhi_buf|=0x04;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 5:  inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_dizhi_buf&=0xF7;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_dizhi_buf|=0x08;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 6:  inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_dizhi_buf&=0xEF;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_dizhi_buf|=0x10;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 7:  inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_dizhi_buf&=0xDF;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_dizhi_buf|=0x20;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 8:	inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_dizhi_buf&=0xBF;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_dizhi_buf|=0x40;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 9:	inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_dizhi_buf&=0x7F;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_dizhi_buf|=0x80;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 10:	inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_dizhichou_buf&=0xFE;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_dizhichou_buf|=0x01;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 11:	inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_dizhichou_buf&=0xFD;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_dizhichou_buf|=0x02;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 12:	inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_dizhichou_buf&=0xFB;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_dizhichou_buf|=0x04;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 13:	inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_dizhichou_buf&=0xF7;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_dizhichou_buf|=0x08;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 14:	inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_dizhichou_buf&=0xEF;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_dizhichou_buf|=0x10;}
					 else{inf_gongcuowu();}              //公共错误处理
                break;
       case 15:	inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_dizhichou_buf&=0xDF;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_dizhichou_buf|=0x20;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 16:	inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_dizhichou_buf&=0xBF;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_dizhichou_buf|=0x40;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 17:	inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_dizhichou_buf&=0x7F;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_dizhichou_buf|=0x80;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
      case 18:	inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_shuju_buf&=0xFE; }
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_shuju_buf|=0x01;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 19:	inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_shuju_buf&=0xFD;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_shuju_buf|=0x02;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 20:	inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_shuju_buf&=0xFB;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_shuju_buf|=0x04;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 21:	inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_shuju_buf&=0xF7;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_shuju_buf|=0x08;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 22:	inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_shuju_buf&=0xEF;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_shuju_buf|=0x10;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 23:	inf_gonggong();
	   				
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_shuju_buf&=0xDF;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_shuju_buf|=0x20;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 24:	inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_shuju_buf&=0xBF;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_shuju_buf|=0x40;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 25:	inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_shuju_buf&=0x7F;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_shuju_buf|=0x80;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 26:	inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_shujuf_buf&=0xFE;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_shujuf_buf|=0x01;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 27:	inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_shujuf_buf&=0xFD;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_shujuf_buf|=0x02;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 28:	inf_gonggong();
	                 
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_shujuf_buf&=0xFB;}					   				
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_shujuf_buf|=0x04;	}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 29:	inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_shujuf_buf&=0xF7;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_shujuf_buf|=0x08;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 30:	inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_shujuf_buf&=0xEF;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_shujuf_buf|=0x10;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 31:	inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_shujuf_buf&=0xDF;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_shujuf_buf|=0x20;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 32:	inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_shujuf_buf&=0xBF;}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_shujuf_buf|=0x40;}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
       case 33:
                inf_gonggong();
                     if(inf_zanshi<inf_lingzhi_h)        //如小于0码最大值则说明是0
                     {inf_shujuf_buf&=0x7F;
                      inf_wancheng();}
                     else if(inf_zanshi<inf_yizhi_h)
                     {inf_shujuf_buf|=0x80;
                      inf_wancheng();}
                     else{inf_gongcuowu();}              //公共错误处理
                break;
           default:
                     inf_shunxu = 0;
                     break;
            }
        }
    }
}




#endif




