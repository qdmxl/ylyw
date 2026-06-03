//基础子程序
#include <math.h>
//#include "REG15W4Kxx.h"
#include "delay.h"
#include "main.h"
#include "basal.h"

//#############################################################################
// 函数名称：void qianshou_1()
// 函数说明：千手单手整齐
// 入口参数：无
// 出口参数：无
//#############################################################################
void qianshou_1()
{
         uchar j;
              for(j=0;j<50;j++)                           //左手抬起
			    {
			     position[12]-=2;
				 PWM_24();
				 low_level_500u(40);
				}   
				 PWM_24();
			        delay500ms(1);

              for(j=0;j<50;j++)
			    {
			     position[12]-=2;
				  PWM_24();
				  low_level_500u(40);
			    }
                    delay500ms(1);

			  
              for(j=0;j<50;j++)                           //左手放下
			    {
			     position[12]+=2;
				  PWM_24();
				 low_level_500u(40);
			    }
			        delay500ms(1);

              for(j=0;j<50;j++)
			    {
			     position[12]+=2;
				  PWM_24();
				  low_level_500u(40);
			    }
                    delay500ms(1);


			  for(j=0;j<50;j++)                           //右手抬起
			    {
			     position[14]+=2;
				  PWM_24();
				 low_level_500u(40);
				}
			        delay500ms(1);

              for(j=0;j<50;j++)
			    {
			     position[14]+=2;
				  PWM_24();
				   low_level_500u(40);
			    }
                    delay500ms(1);


              for(j=0;j<50;j++)                           //右手放下
			    {
			     position[14]-=2;
				  PWM_24();
				   low_level_500u(40);
				 }
			        delay500ms(1);

              for(j=0;j<50;j++)
			    {
			     position[14]-=2;
				  PWM_24();
				   low_level_500u(40);
		    	 }
                    delay500ms(1);

}//#############################################################################
// 函数名称：void qianshou_2()
// 函数说明：千手单手前后
// 入口参数：无
// 出口参数：无
//#############################################################################
void qianshou_2()
{
         uchar j;

		     ForwardDelay();                         //调用千手步前延时子程序
			  for(j=0;j<200;j++)                           //左手抬起
			    {
			     position[12]-=1;
				  PWM_24();
				 low_level_500u(40);
				}
			       
              for(j=0;j<200;j++)                           //左手放下
			    {
			     position[12]+=1;
				  PWM_24();
				 low_level_500u(40);
			    }
			       
			  for(j=0;j<200;j++)                           //右手抬起
			    {
			     position[14]+=1;
				  PWM_24();
				 low_level_500u(40);
				}
			        
              for(j=0;j<200;j++)                           //右手放下
			    {
			     position[14]-=1;
				  PWM_24();
				   low_level_500u(40);
				 }
			   BackDelay();     
                 

}//#############################################################################
// 函数名称：void qianshou_3()
// 函数说明：千手双手前后
// 入口参数：无
// 出口参数：无
//#############################################################################
void qianshou_3(uchar number)
{
         uchar j,i;
		      for(j=0;j<100;j++)                           //双手举平
			    {
			     position[12]-=1;
				 position[14]+=1;
				  PWM_24();
				 low_level_500u(40);
			    }

                 ForwardDelay();                         //调用千手步前延时子程序                 

           for(i=0;i<number;i++)
             {

			  for(j=0;j<100;j++)                           //左手抬高，右手放下
			    {
			     position[12]-=1;
				 position[14]-=1;
				  PWM_24();
				 low_level_500u(40);
			    }
                    delay1s(1);

			  for(j=0;j<100;j++)                           //双手举平
			    {
			     position[12]+=1;
				 position[14]+=1;
				  PWM_24();
				 low_level_500u(40);
			    }

			  for(j=0;j<100;j++)                           //右手抬高，左手放下
			    {
			     position[12]+=1;
				 position[14]+=1;
				  PWM_24();
				 low_level_500u(40);
			    }
                     delay1s(1);

              for(j=0;j<100;j++)                           //双手举平
			    {
			     position[12]-=1;
				 position[14]-=1;
				  PWM_24();
				   low_level_500u(40);
				 }
              }

                 BackDelay();                    //调用千手步后延时子程序

              for(j=0;j<100;j++)                           //双手放下
			    {
			     position[12]+=1;
				 position[14]-=1;
				  PWM_24();
				   low_level_500u(40);
				 }
}//#############################################################################
// 函数名称：void qianshou_4()
// 函数说明：千手双手弯曲
// 入口参数：无
// 出口参数：无
//#############################################################################
void qianshou_4(uchar number)
{
         uchar j,i;

		      for(j=0;j<100;j++)                           //双手举平
			    {
			     position[12]-=1;
				 position[14]+=1;
				  PWM_24();
				 low_level_500u(40);
				}
		      for(j=0;j<100;j++)                           //肩膀高，胳膊平
			    {
			     position[12]-=1;
				 position[14]+=1;
                 position[13]+=1;
				 position[15]-=1;
				  PWM_24();
				   low_level_500u(40);
				 }

              for(j=0;j<100;j++)                           //肩膀平，胳膊平（双手举平）
			    {
			     position[12]+=1;
				 position[14]-=1;
                 position[13]-=1;
				 position[15]+=1;
				  PWM_24();
				   low_level_500u(40);
				 }

              for(j=0;j<100;j++)                           //肩膀低，胳膊平
			    {
			     position[12]+=1;
				 position[14]-=1;
                 position[13]-=1;
				 position[15]+=1;
				  PWM_24();
				   low_level_500u(40);
				 }
				   ForwardDelay();                         //调用千手步前延时子程序
			   
			  
			  for(j=0;j<100;j++)                           //肩膀平，胳膊平（双手举平）
			    {
			     position[12]-=1;
				 position[14]+=1;
                 position[13]+=1;
				 position[15]-=1;
				  PWM_24();
				   low_level_500u(40);
				 }
		 for(i=0;i<number;i++)                           
		   {
			  for(j=0;j<100;j++)                           //肩膀高，胳膊平
			    {
			     position[12]-=1;
				 position[14]+=1;
                 position[13]+=1;
				 position[15]-=1;
				  PWM_24();
				   low_level_500u(40);
				 }

              for(j=0;j<100;j++)                           //肩膀平，胳膊平（双手举平）
			    {
			     position[12]+=1;
				 position[14]-=1;
                 position[13]-=1;
				 position[15]+=1;
				  PWM_24();
				   low_level_500u(40);
				 }

              for(j=0;j<100;j++)                           //肩膀低，胳膊平
			    {
			     position[12]+=1;
				 position[14]-=1;
                 position[13]-=1;
				 position[15]+=1;
				  PWM_24();
				   low_level_500u(40);
				 }
			  for(j=0;j<100;j++)                           //肩膀平，胳膊平（双手举平）
			    {
			     position[12]-=1;
				 position[14]+=1;
                 position[13]+=1;
				 position[15]-=1;
				  PWM_24();
				   low_level_500u(40);
				}
		   }
		            BackDelay();                         //调用千手步后延时子程序


              for(j=0;j<100;j++)                           //双手放下(复位)
			    {
			     position[12]+=1;
				 position[14]-=1;
				  PWM_24();
				 low_level_500u(40);
				}
			  
}//#############################################################################
// 函数名称：void qianshou_5()
// 函数说明：千手双手圆弧
// 入口参数：无
// 出口参数：无
//#############################################################################
void qianshou_5(uchar number,uchar sudu1)
{
             uchar j,i;
		  for(i=0;i<number;i++)
            {
              for(j=0;j<85;j++)                           //双手举过头，呈圆弧
			    {
			     position[12]-=2;
				 position[14]+=2;
                 position[13]-=1;
				 position[15]+=1;
				  PWM_24();
				 low_level_500u(sudu1);
			    }

              for(j=0;j<85;j++)                           //放下（复位）
			    {
			     position[12]+=2;
				 position[14]-=2;
                 position[13]+=1;
				 position[15]-=1;
				  PWM_24();
				  low_level_500u(sudu1);
			    }
            }
}
//#############################################################################
// 函数名称：void qianshou_6()
// 函数说明：千手角度手
// 入口参数：无
// 出口参数：无
//#############################################################################	   
void qianshou_6()
{
          
            uint i,i1,i2;
				i1=part;
				i2=total;
			      
				ForwardDelay();                         //调用千手步前延时子程序
                ForwardDelay();
				ForwardDelay();                         //调用千手步前延时子程序
        		  
				  i=180*i1/(i2+1);	 				  	  
				
	        relative(0,0,0,0,0,0,0,0,0,0,0,0,(-1)*i,0,i,0,0,0,0,0,0,0,0,0);
	        p_to_p(15,20);

				  
                     BackDelay();                    //调用千手步后延时子程序
                     BackDelay();
					 BackDelay();                    //调用千手步后延时子程序
					 delay1s(2);

			i=180*(i2-i1+1)/(i2+1);
			relative(0,0,0,0,0,0,0,0,0,0,0,0,(-1)*i,0,i,0,0,0,0,0,0,0,0,0);
	        p_to_p(15,20);
		 	delay1s(2);

			
			relative(0,0,0,0,0,0,6,-5,0,0,0,0,10,0,-10,0,0,0,0,0,0,0,0,0);
	        p_to_p(15,20);
			 delay500ms(2);
								 			  
}
//#############################################################################
// 函数名称：void qianshou_7()
// 函数说明：千手圆环
// 入口参数：无
// 出口参数：无
//#############################################################################
void qianshou_7(uchar number)
{
             uchar j,i;
		      for(j=0;j<85;j++)                           //双手举过头，呈圆弧
			    {
			     position[12]-=2;
				 position[14]+=2;
                 position[13]-=1;
				 position[15]+=1;
				  PWM_24();
				 low_level_500u(40);
				}

				    ForwardDelay();                         //调用千手步前延时子程序
	 
		 for(i=0;i<number;i++)                           
		   {	    
			  for(j=0;j<50;j++)                           
			    {
			     position[0]-=1;
				 position[1]+=2;
                 position[2]+=1;
				 position[3]+=1;
				 position[4]-=2;
				 position[5]-=1;
				  PWM_24();
				low_level_500u(50);
				}
				  BackDelay();                            //调用千手步后延时子程序
				  ForwardDelay();                         //调用千手步前延时子程序
			  for(j=0;j<50;j++)                           
			    {
			     position[0]+=1;
				 position[1]-=2;
                 position[2]-=1;
				 position[3]-=1;
				 position[4]+=2;
				 position[5]+=1;
				  PWM_24();
				low_level_500u(50);
				}
		   }   
	 
		          BackDelay();                    //调用千手步后延时子程序
			  for(j=0;j<(10*(total-part));j++)                           
			    {
			     position[0]-=1;
				 position[1]+=2;
                 position[2]+=1;
				 position[3]+=1;
				 position[4]-=2;
				 position[5]-=1;
				  PWM_24();
				 low_level_500u(40);
				}
			  for(j=0;j<(total*part);j++)                           
			    {
			     position[0]-=0;
				 position[1]+=0;
                 position[2]+=0;
				 position[3]+=0;
				 position[4]-=0;
				 position[5]-=0;
				  PWM_24();
				 low_level_500u(40);
				}
 
			  for(j=0;j<5;j++)                           //
			    {
			     position[12]+=14;
				 position[14]-=14;
                 position[13]+=17;
				 position[15]-=17;
				  PWM_24();
				 low_level_500u(70);
				}
				   delay10ms(20);
			        ForwardDelay();                         //调用千手步前延时子程序

		for(i=0;i<number;i++)                           
		   {
			  for(j=0;j<100;j++)                           //肩膀高，胳膊平
			    {
			     position[12]-=1;
				 position[14]+=1;
                 position[13]+=1;
				 position[15]-=1;
				  PWM_24();
				   low_level_500u(40);
				 }

              for(j=0;j<100;j++)                           //肩膀平，胳膊平（双手举平）
			    {
			     position[12]+=1;
				 position[14]-=1;
                 position[13]-=1;
				 position[15]+=1;
				  PWM_24();
				   low_level_500u(40);
				 }

              for(j=0;j<100;j++)                           //肩膀低，胳膊平
			    {
			     position[12]+=1;
				 position[14]-=1;
                 position[13]-=1;
				 position[15]+=1;
				  PWM_24();
				   low_level_500u(40);
				 }
			  for(j=0;j<100;j++)                           //肩膀平，胳膊平（双手举平）
			    {
			     position[12]-=1;
				 position[14]+=1;
                 position[13]+=1;
				 position[15]-=1;
				  PWM_24();
				   low_level_500u(40);
				}
		   }
	 
                     BackDelay();                       //调用千手步后延时子程序
			  for(j=0;j<(total*part);j++)                           
			    {
			     position[0]+=0;
				 position[1]-=0;
                 position[2]-=0;
				 position[3]-=0;
				 position[4]+=0;
				 position[5]+=0;
				  PWM_24();
				 low_level_500u(40);
				} 
 
			  for(j=0;j<(10*(total-part));j++)                           
			    {
			     position[0]+=1;
				 position[1]-=2;
                 position[2]-=1;
				 position[3]-=1;
				 position[4]+=2;
				 position[5]+=1;
				  PWM_24();
				 low_level_500u(40);
				}
	  
              for(j=0;j<100;j++)                           //双手放下(复位)
			    {
			     position[12]+=1;
				 position[14]-=1;
				  PWM_24();
				 low_level_500u(40);
				}
} 
//#############################################################################
// 函数名称：void qianshou_8()
// 函数说明：千手弧度侧身
// 入口参数：无
// 出口参数：无
//###############################################################################
void qianshou_8()
{
          
             uchar j;
			  for(j=0;j<85;j++)                           //双手举过头，呈圆弧
			    {
			     position[12]-=2;
				 position[14]+=2;
                 position[13]-=1;
				 position[15]+=1;
				  PWM_24();
				  low_level_500u(40);
				}

				    ForwardDelay();                         //调用千手步前延时子程序

			  for(j=0;j<15;j++)                           //身体右侧
			    {
			     position[8]+=1;
				 position[9]-=1;
                 position[10]+=1;
				 position[11]-=1;
				  PWM_24();
				  low_level_500u(60);
				}

				      delay1s(2);
					  
			  for(j=0;j<30;j++)                           //身体左侧
			    {
			     position[8]-=1;
				 position[9]+=1;
                 position[10]-=1;
				 position[11]+=1;
				  PWM_24();
				  low_level_500u(60);
				}

				      delay1s(1);
					 
			  for(j=0;j<15;j++)                           //身体居中
			    {
			     position[8]+=1;
				 position[9]-=1;
                 position[10]+=1;
				 position[11]-=1;
				  PWM_24();
				  low_level_500u(60);
				}

				      BackDelay();                    //调用千手步后延时子程序

			  for(j=0;j<85;j++)                           //双手放下（复位）
			    {
			     position[12]+=2;
				 position[14]-=2;
                 position[13]+=1;
				 position[15]-=1;
				  PWM_24();
				  low_level_500u(40);
			    } 			  
}
//#############################################################################
// 函数名称：void qianshou_9()
// 函数说明：千手双上手前后
// 入口参数：无
// 出口参数：无
//#############################################################################
void qianshou_9(uchar number)
{
          
             uchar j,i;
			  
		  for(i=0;i<number;i++)
            {
			       ForwardDelay();                        //调用千手步前延时子程序
              for(j=0;j<85;j++)                           //双手举过头，呈圆弧
			    {
			     position[12]-=2;
				 position[14]+=2;
                 position[13]-=1;
				 position[15]+=1;
				  PWM_24();
				 low_level_500u(70);
			    }
				  BackDelay();                           //调用千手步后延时子程序
				  ForwardDelay();                        //调用千手步前延时子程序
              for(j=0;j<85;j++)                           //放下（复位）
			    {
			     position[12]+=2;
				 position[14]-=2;
                 position[13]+=1;
				 position[15]-=1;
				  PWM_24();
				 low_level_500u(70);
			    }
				  BackDelay();                         //调用千手步前延时子程序
            }

		  for(i=0;i<number;i++)
            {
			       ForwardDelay();                        //调用千手步前延时子程序
              for(j=0;j<85;j++)                           //双手举过头，呈圆弧
			    {
			     position[12]-=2;
				 position[14]+=2;
                 position[13]-=1;
				 position[15]+=1;
				  PWM_24();
				 low_level_500u(70);
			    }
			  for(j=0;j<85;j++)                           //放下（复位）
			    {
			     position[12]+=2;
				 position[14]-=2;
                 position[13]+=1;
				 position[15]-=1;
				  PWM_24();
				 low_level_500u(70);
			    }
				  BackDelay();                         //调用千手步前延时子程序
            }
}//#############################################################################
// 函数名称：void qianshou_10()
// 函数说明：千手双手弯曲
// 入口参数：无
// 出口参数：无
//#############################################################################
void qianshou_10(uchar number)
{
         uchar j,i;

		      for(j=0;j<100;j++)                           //双手举平
			    {
			     position[12]-=1;
				 position[14]+=1;
				  PWM_24();
				 low_level_500u(40);
				}
		      for(j=0;j<100;j++)                           //肩膀高，胳膊平
			    {
			     position[12]-=1;
				 position[14]-=1;
                 position[13]+=1;
				 position[15]+=1;
				  PWM_24();
				   low_level_500u(40);
				 }

              for(j=0;j<100;j++)                           //肩膀平，胳膊平（双手举平）
			    {
			     position[12]+=1;
				 position[14]+=1;
                 position[13]-=1;
				 position[15]-=1;
				  PWM_24();
				   low_level_500u(40);
				 }

              for(j=0;j<100;j++)                           //肩膀低，胳膊平
			    {
			     position[12]+=1;
				 position[14]+=1;
                 position[13]-=1;
				 position[15]-=1;
				  PWM_24();
				   low_level_500u(40);
				 }
				   ForwardDelay();                         //调用千手步前延时子程序
			   
			  
			  for(j=0;j<100;j++)                           //肩膀平，胳膊平（双手举平）
			    {
			     position[12]-=1;
				 position[14]-=1;
                 position[13]+=1;
				 position[15]+=1;
				  PWM_24();
				   low_level_500u(40);
				 }
		 for(i=0;i<number;i++)                           
		   {
			  for(j=0;j<100;j++)                           //肩膀高，胳膊平
			    {
			     position[12]-=1;
				 position[14]-=1;
                 position[13]+=1;
				 position[15]+=1;
				  PWM_24();
				   low_level_500u(40);
				 }

              for(j=0;j<100;j++)                           //肩膀平，胳膊平（双手举平）
			    {
			     position[12]+=1;
				 position[14]+=1;
                 position[13]-=1;
				 position[15]-=1;
				  PWM_24();
				   low_level_500u(40);
				 }

              for(j=0;j<100;j++)                           //肩膀低，胳膊平
			    {
			     position[12]+=1;
				 position[14]+=1;
                 position[13]-=1;
				 position[15]-=1;
				  PWM_24();
				   low_level_500u(40);
				 }
			  for(j=0;j<100;j++)                           //肩膀平，胳膊平（双手举平）
			    {
			     position[12]-=1;
				 position[14]-=1;
                 position[13]+=1;
				 position[15]+=1;
				  PWM_24();
				   low_level_500u(40);
				}
		   }
		            BackDelay();                         //调用千手步后延时子程序


              for(j=0;j<100;j++)                           //双手放下(复位)
			    {
			     position[12]+=1;
				 position[14]-=1;
				  PWM_24();
				 low_level_500u(40);
				}	  			  
}
//#############################################################################
// 函数名称：void qianshou()
// 函数说明：千手观音
// 参    数：无
// 返 回 值：无
//#############################################################################
void qianshou()
{	           
             uchar j;
              for(j=0;j<5;j++)                         //千手准备程序
			    {
			     position[12]+=2;
				 position[14]-=2;
				 position[6]+=1;
				 position[7]-=1;
					 PWM_24();
				  low_level_500u(25);
				}

                   delay1s(1);

                    qianshou_1();
					qianshou_2();
					qianshou_3(2);                     //括号里面的表示次数
					qianshou_4(2);					   //括号里面的表示次数
					qianshou_9(2);					   //括号里面的表示次数
					qianshou_10(2);                    //括号里面的表示次数
					qianshou_5(1,60);
					qianshou_5(1,50);
					qianshou_5(1,40);
				    qianshou_5(1,30);
					qianshou_5(1,60);
                    delay500ms(1);
				 	qianshou_6();
					qianshou_7(2);
					qianshou_8();
			  
			  for(j=0;j<5;j++)                            //双手还原
			    {
			     position[12]-=3;
				 position[14]+=3;
				 position[6]-=1;
				 position[7]+=1;
				  PWM_24();
                   low_level_500u(25);
				}
                delay500ms(1); 		    
}

