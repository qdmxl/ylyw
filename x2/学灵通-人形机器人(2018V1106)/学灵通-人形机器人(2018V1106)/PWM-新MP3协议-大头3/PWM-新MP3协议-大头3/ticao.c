#include "delay.h"
#include "qianshou.h"
#include "basal.h"
#include "jiewu.h"
#include "walking.h"
#include "main.h"
//#############################################################################
// 函数名称：void xq_td()
// 函数说明：胸前头顶摆动
// 入口参数：无
// 出口参数：无
//#############################################################################		 
void xq_td(void)
{            uchar j,i;
  for(i=0;i<30;i++)
		      {
			   position[0]-=2;             
			   position[3]+=2;             
			   position[2]-=1;             
			   position[5]+=1;              	   
			   position[6]-=1;             
			   position[7]+=1;             
			   position[12]-=2;            
               position[13]+=2;             
			   position[14]+=2;              
			   position[15]-=2;             
			   PWM_24();
               low_level_500u(30);
		      }

		    for(i=0;i<10;i++)
		      {
               position[13]-=6;             
			   position[15]-=6;               
			   position[16]+=2;             
               PWM_24();
               low_level_500u(30);
		      }
	     for(j=0;j<2;j++)
		   {			
		    for(i=0;i<20;i++)
		      {
               position[13]+=6;               
			   position[15]+=6;               
			   position[16]-=2;             
               PWM_24();
              low_level_500u(30);
		      }	
			    delay10ms(20);			    
		    for(i=0;i<20;i++)
		      {
               position[13]-=6;            
			   position[15]-=6;             
			   position[16]+=2;             
               PWM_24();
              low_level_500u(30);
		      }
		  }
		    for(i=0;i<10;i++)
		      {
               position[13]+=6;            
			   position[15]+=6;            
			   position[16]-=2;            
               PWM_24();
               low_level_500u(30);
		      }	
		 	   
			for(i=0;i<30;i++)
		      {
			   position[0]+=2;             
			   position[3]-=2;              
			   position[2]+=1;              
			   position[5]-=1;              		   
			   PWM_24();
               low_level_500u(30);
		      }  delay10ms(20);	              //胸前摆动
		    delay10ms(50);
			for(i=0;i<60;i++)
		      {
			   position[6]-=3;              
			   position[7]+=3;              
			   position[12]+=1;             
			   position[14]-=1;            			   		   
			   PWM_24();
               low_level_500u(30);
		      } 
	     for(j=0;j<2;j++)
		   {
			for(i=0;i<30;i++)
		      {
               position[13]-=3;             
			   position[15]+=3;            
			   position[16]+=1;             
               PWM_24();
               low_level_500u(30);
		      }	
			for(i=0;i<30;i++)
		      {
               position[13]+=3;              
			   position[15]-=3;              
			   position[16]-=1;             
               PWM_24();
               low_level_500u(30);
		      }
		  }	
		           delay10ms(20);            //头顶摆动

  for(i=0;i<10;i++)
		      {
               position[8]-=1;             
			   position[9]+=1;             
			   position[10]-=1;             
			   position[11]+=1;             
			   position[12]+=1;              
			   position[14]+=1;             
              PWM_24();
                    low_level_500u(75);
		      }
	  for(j=0;j<2;j++)
		   {
			for(i=0;i<20;i++)
		      {
               position[8]+=1;              
			   position[9]-=1;             
			   position[10]+=1;            
			   position[11]-=1;             
			   position[12]-=1;            
			   position[14]-=1;             
                   PWM_24();
                    low_level_500u(75);
		      }
			for(i=0;i<20;i++)
		      {
               position[8]-=1;               
			   position[9]+=1;              
			   position[10]-=1;             
			   position[11]+=1;             
			   position[12]+=1;            
			   position[14]+=1;            
                   PWM_24();
                    low_level_500u(75);
		      }
		   }
			for(i=0;i<10;i++)
		      {
               position[8]+=1;             
			   position[9]-=1;             
			   position[10]+=1;           
			   position[11]-=1;            
			   position[12]-=1;            
			   position[14]-=1;            
                 PWM_24();
                    low_level_500u(75);
		      }
			for(i=0;i<10;i++)
		      {
               position[6]+=21;             
			   position[7]-=21;             
			   position[12]-=6;             
			   position[14]+=6;             
                  PWM_24();
                    low_level_500u(75);
		      }
			    delay10ms(20);            //头顶摆动
  for(j=0;j<3;j++)
		   {
			for(i=0;i<10;i++)
		      {
               position[9]-=2;            
			   position[11]+=2;            
			   position[12]-=3;            
			   position[13]+=3;             
			   position[14]+=3;              
			   position[15]-=3;             
                  PWM_24();
                    low_level_500u(75);
		      }
			for(i=0;i<10;i++)
		      {
               position[9]+=2;             
			   position[11]-=2;             
			   position[12]+=3;              
			   position[13]-=3;             
			   position[14]-=3;              
			   position[15]+=3;              
             PWM_24();
                    low_level_500u(75);
		      }
			        delay10ms(20); 
		  }      
		    for(i=0;i<24;i++)
			{position_change[i]=position_initial[i]-position[i];}
			p_to_p(55,40);				   
		   
			 delay10ms(100); 
			jingli_l();			
}
//#############################################################################
// 函数名称：void cs_xd_left()
// 函数说明：侧身下蹲，头向左扭
// 入口参数：无
// 出口参数：无
//#############################################################################
void cs_xd_left(void)                         
{
  uchar i;
   for(i=0;i<55;i++)
   {
      position[12]-=2;
      position[14]+=2;        
	 PWM_24();
     low_level_500u(30);
   }
        
 for(i=0;i<20;i++)
		      {
		         position[8]+=1;              
		         position[9]-=1; 
             
		         position[10]+=1;
		         position[11]-=1;

		         position[16]+=1;

		         PWM_24();
                 low_level_500u(45);
		     }
	  for(i=0;i<60;i++)
		      {
		         position[3]+=1;              
		         position[4]-=2;              
		         position[5]-=1;              

		        

                 if((i%2)==0)
		         { position[16]+=1;
                    position[8]+=1;
		            position[9]-=1;
	   	         }

		         if((i%4)==0)
		         {
		            position[3]+=1;            
					position[4]-=1;              
		         }

		       PWM_24();
                    low_level_500u(45);
              }		 


        for(i=0;i<60;i++)
		      {
		         position[3]-=1;              
		         position[4]+=2;              
		         position[5]+=1;              

                if((i%2)==0)
		         {position[16]-=1;
                    position[8]-=1;
		            position[9]+=1;
	   	         }

		         if((i%4)==0)
		         {
		            position[3]-=1;              
     	            position[4]+=1;              
		         }

		       PWM_24();
                    low_level_500u(45);
              }
   
   for(i=0;i<20;i++)
		      {
		         position[8]-=1;              
		         position[9]+=1; 
             
		         position[10]-=1;
		         position[11]+=1;

		         position[16]-=1;

		        PWM_24();
                    low_level_500u(45);
		     
		      }
   
   for(i=0;i<55;i++)
   {
      position[12]+=2;
	  position[14]-=2;
     PWM_24();
       low_level_500u(30);
   }
}
//#############################################################################
// 函数名称：void cs_xd_right()
// 函数说明：侧身下蹲，头向右扭
// 入口参数：无
// 出口参数：无
//#############################################################################

void cs_xd_right(void)                          
{
   uchar i;
   for(i=0;i<55;i++)
   {
      position[12]-=2;
	  position[14]+=2;
           
	  PWM_24();
      low_level_500u(30);
				
   }

 for(i=0;i<20;i++)
		      {
		         position[8]-=1;              
		         position[9]+=1; 
             
		         position[10]-=1;
		         position[11]+=1;

		         position[16]-=1;

		        PWM_24();
                    low_level_500u(45);
		     
		      }
 for(i=0;i<60;i++)
		      {
		         position[0]-=1;              
		         position[1]+=2;              
		         position[2]+=1;              

		        

                 if((i%2)==0)
		         { position[16]-=1;
                    position[10]-=1;
		            position[11]+=1;
	   	         }

		         if((i%4)==0)
		         {
		            position[0]-=1;             
		            position[1]+=1;             
		         }

		       PWM_24();
                    low_level_500u(45);
              }

 for(i=0;i<60;i++)
		      {
		         position[0]+=1;              
		         position[1]-=2;              
		         position[2]-=1;              

                 if((i%2)==0)
		         {position[16]+=1;
                    position[10]+=1;
		            position[11]-=1;
	   	         }

		         if((i%4)==0)
		         {
		            position[0]+=1;              
		            position[1]-=1;              
		         }

		       PWM_24();
                    low_level_500u(45);
              }
 for(i=0;i<20;i++)
		      {
		         position[8]+=1;              
		         position[9]-=1; 
             
		         position[10]+=1;
		         position[11]-=1;

		         position[16]+=1;

		        PWM_24();
                    low_level_500u(45);
		     
		      }

   for(i=0;i<55;i++)
   {
      position[12]+=2;
	  position[14]-=2;
           
     PWM_24();
      low_level_500u(30);
				
   }
}

//#############################################################################
// 函数名称：void py_ss_left(void) 
// 函数说明：左平移手展开
// 入口参数：无
// 出口参数：无
//#############################################################################

void py_ss_left(void)             //左平移手展开
{uchar i,j;

   sit_down(35);
    for(j=0;j<3;j++) 
	  {
	 	 for(i=0;i<15;i++)             //向右侧身
		 {
			position[8]+=1;           
			position[9]-=1;           
			
            position[10]+=1;           
			position[11]-=1;           

		    position[13]-=4;
            position[15]+=4;
            PWM_24();
            low_level_500u(45);
		 }  
         for(i=0;i<10;i++)                 
		 {
            position[0]-=1;                    
			position[1]+=2;               
			position[2]+=1;               
			position[8]+=1;               
			position[9]-=1;               

			position[13]-=3;
            position[15]+=3;
              
			PWM_24();
            low_level_500u(45);
		 }

	     for(i=0;i<10;i++)                
		 {
            position[0]+=1;               
			position[1]-=2;
			position[2]-=1;
			position[8]+=1;               
			position[9]-=1;               

			position[13]-=2;
            position[15]+=2;
              
			PWM_24();
                    low_level_500u(45);
		 }
//---------------------------------------------------------------------------------
         for(i=0;i<50;i++)             
		 {
			position[8]-=1;            
			position[9]+=1;            

            position[10]-=1;           
			position[11]+=1;                          

		    position[13]++;
            position[15]--;

	        position[12]--;
		    position[14]++;

			PWM_24();
                    low_level_500u(45);
   		 }
	     for(i=0;i<20;i++)             
		 {
			position[10]+=1;            
			position[11]-=1;            
			                
            position[13]+=2;
            position[15]-=2;

			position[12]-=2;
		    position[14]+=2;
				
			PWM_24();
                    low_level_500u(45);
   		 }
	     for(i=0;i<15;i++)             //向右侧身
		 {
			position[8]+=1;           
			position[9]-=1;           

            position[10]+=1;          
			position[11]-=1;          

	        position[13]+=1;
            position[15]-=1;

			position[12]-=1;
		    position[14]+=1;

            if((i%3)==0)
			{
			   position[13]++;
               position[15]--;

			   position[12]--;
		       position[14]++;
			}
               
			PWM_24();
                    low_level_500u(45);
		 }


        for(i=0;i<55;i++)                   
		{
		  position[12]+=2;
		  position[14]-=2;
		  PWM_24();
          low_level_500u(45);
        }
	
     }
   stand_up(35);
  }  
//#############################################################################
// 函数名称：void py_ss_right(void) 
// 函数说明：右平移手展开
// 入口参数：无
// 出口参数：无
//#############################################################################
void py_ss_right(void)             //右平移手展开
{uchar i,j;
   sit_down(35);

   for(j=0;j<3;j++) 
	  {
	 	 for(i=0;i<15;i++)                   //向右侧身
		 {
			position[8]-=1;            
			position[9]+=1;            

            position[10]-=1;           
			position[11]+=1;           

		    position[13]-=4;
            position[15]+=4;
           PWM_24();
                    low_level_500u(45);
		 }  
         for(i=0;i<10;i++)                 
		 {
            position[3]+=1;                    
			position[4]-=2;               
			position[5]-=1;               
			position[10]-=1;              
			position[11]+=1;              

			position[13]-=3;
            position[15]+=3;
              
			PWM_24();
                    low_level_500u(45);
		 }

	     for(i=0;i<10;i++)                
		 {
            position[3]-=1;              
			position[4]+=2;
			position[5]+=1;
			position[10]-=1;               
			position[11]+=1;              

			position[13]-=2;
            position[15]+=2;
              
			PWM_24();
                    low_level_500u(45);
		 }
//---------------------------------------------------------------------------------
         for(i=0;i<50;i++)             
		 {
			position[8]+=1;            
			position[9]-=1;            

            position[10]+=1;           
			position[11]-=1;                          

		    position[13]++;
            position[15]--;

	        position[12]--;
		    position[14]++;

			PWM_24();
             low_level_500u(45);
   		 }
	     for(i=0;i<20;i++)             
		 {
			position[8]-=1;            
			position[9]+=1;            
                
            position[13]+=2;
            position[15]-=2;

			position[12]-=2;
		    position[14]+=2;
				
			PWM_24();
                    low_level_500u(45);
   		 }
	     for(i=0;i<15;i++)                   //向右侧身
		 {
			position[8]-=1;            
			position[9]+=1;            

            position[10]-=1;           
			position[11]+=1;           
			
	        position[13]+=1;
            position[15]-=1;

			position[12]-=1;
		    position[14]+=1;

            if((i%3)==0)
			{
			   position[13]++;
               position[15]--;

			   position[12]--;
		       position[14]++;
			}
               
			PWM_24();
                    low_level_500u(45);
		 }


        for(i=0;i<55;i++)                   
		{
		  position[12]+=2;
		  position[14]-=2;
		 PWM_24();
                    low_level_500u(45);
        }
		
     }
  stand_up(35);           
}     

//#############################################################################
// 函数名称：void tice_yd(void)  
// 函数说明：体侧运动
// 入口参数：无
// 出口参数：无
//#############################################################################
void tice_yd(void)                //体侧运动
{
   uchar i,j;

   position[12]=position_initial[12]-110;
   position[14]=position_initial[14]+110;
       PWM_24();
       low_level_500u(55);
	   delay10ms(65);

   position[7]=position_initial[7]+200;
      PWM_24();
      low_level_500u(65);
	  delay10ms(45);

	 for(i=0;i<70;i++)
    {
       position[12]+=1;
	   position[13]+=1;
	   position[14]-=1;

	   if((i%4)==0)
	   {
		  position[8]+=1;
		  position[9]-=1;
		  position[10]+=1;
          position[11]-=1;
	   }
  PWM_24();
      low_level_500u(20);
     }
	
   for(j=0;j<2;j++)
   {
	   for(i=0;i<40;i++)
       {
		  position[14]-=1;
          position[15]-=2;
         PWM_24();
      low_level_500u(40);
	   }

	   for(i=0;i<40;i++)
       {	  
          position[14]+=1;
          position[15]+=2;
        PWM_24();
      low_level_500u(40);
	   }
   }

    for(i=0;i<70;i++)
    {
       position[12]-=1;
	   position[13]-=1;
	   position[14]+=1;

	   if((i%4)==0)
	   {
		  position[8]-=1;
		  position[9]+=1;
		  position[10]-=1;
          position[11]+=1;
	   }
  PWM_24();
      low_level_500u(20);
}

   position[6]=position_initial[6]-200;
   position[7]=position_initial[7]-230;
      PWM_24();
      low_level_500u(55);
	  delay10ms(65);
      
    for(i=0;i<70;i++)
    {
       position[14]-=1;
	   position[15]-=1;
	   position[12]+=1;

	   if((i%4)==0)
	   {
		  position[8]-=1;
		  position[9]+=1;
		  position[10]-=1;
          position[11]+=1;
	   }
  PWM_24();
      low_level_500u(20);
  }
       for(j=0;j<2;j++)
   {
	   for(i=0;i<40;i++)
       {
		  position[12]+=1;
          position[13]+=2;
         PWM_24();
      low_level_500u(40);
	   }

	   for(i=0;i<40;i++)
       {	  
          position[12]-=1;
          position[13]-=2;
        PWM_24();
      low_level_500u(40);
	   }
   }

 
  for(i=0;i<70;i++)
    {
       position[14]+=1;
	   position[15]+=1;
	   position[12]-=1;

	   if((i%4)==0)
	   {
		  position[8]+=1;
		  position[9]-=1;
		  position[10]+=1;
          position[11]-=1;
	   }
  PWM_24();
      low_level_500u(20);
}
   position[7]=position_initial[7]+200;
   PWM_24();
      low_level_500u(20);
   delay1s(1);
  
//-----------------------------------------------------------------------------------
        for(j=0;j<3;j++)
        {   
		  for(i=0;i<30;i++)
          {
           position[12]+=3;
		   position[13]+=3;
		   position[14]-=3;
           position[15]-=3;
             PWM_24();
                    low_level_500u(25);
			}
           
		 
		  for(i=0;i<45;i++)
          {position[12]-=2;
		   position[13]-=2;
		   position[14]+=2;
           position[15]+=2;
           PWM_24();
           low_level_500u(45);				
          }		   
	}

   delay500ms(1);

   position[6]=position_initial[6];
   position[7]=position_initial[7];
    PWM_24();
      low_level_500u(20);
				
   delay1s(1);

   for(i=0;i<55;i++)
   {
	  position[12]+=2;
      position[14]-=2;
	  PWM_24();
      low_level_500u(20);				
   }
    delay500ms(1);
}
//#############################################################################
// 函数名称：void shenzhan()
// 函数说明：伸展运动
// 入口参数：无
// 出口参数：无
//#############################################################################
void shenzhan(void)
{ uchar i;
 position_change[7]=210;
  position_change[12]=-100;
  position_change[14]=100;
   position_change[16]=-50;
 p_to_p(40,0);
 
 delay500ms(1);
 for(i=0;i<3;i++)
 {
 position_change[8]=5;
 position_change[9]=-5;
 position_change[10]=5;
 position_change[11]=-5;
 
 position_change[12]=40;
 position_change[14]=-40;

 p_to_p(30,0);
 delay10ms(1);
 position_change[8]=-5;
 position_change[9]=5;
 position_change[10]=-5;
 position_change[11]=5;
 
 position_change[12]=-40;
 position_change[14]=40;

 p_to_p(30,0);
  delay10ms(1);
 }

  position_change[7]=-210;
  position_change[12]=100;
  position_change[14]=-100;
  position_change[16]=50;
 p_to_p(40,0);
 delay500ms(1);
 ////////////////////////////////////////////////////////////////////
   position_change[6]=-210;
  position_change[12]=-100;
  position_change[14]=100;
   position_change[16]=50;
 p_to_p(40,0);
 delay500ms(1);
 for(i=0;i<3;i++)
 {
 position_change[8]=-5;
 position_change[9]=5;
 position_change[10]=-5;
 position_change[11]=5;
 
 position_change[12]=40;
 position_change[14]=-40;
delay10ms(1);
 p_to_p(30,0);
 
 position_change[8]=5;
 position_change[9]=-5;
 position_change[10]=5;
 position_change[11]=-5;
 
 position_change[12]=-40;
 position_change[14]=40;

 p_to_p(30,0);
 delay10ms(1);
 }
  position_change[6]=210;
  position_change[12]=100;
  position_change[14]=-100;
   position_change[16]=-50;
 p_to_p(40,0);
 delay500ms(1);

}
//#############################################################################
// 函数名称：void kuoxiong()
// 函数说明：扩胸运动
// 入口参数：无
// 出口参数：无
//#############################################################################

void kuoxiong(void)
{uchar i;
position_change[6]=-110;
position_change[7]=110;
p_to_p(20,0);
delay10ms(1);
position_change[12]=-130;
position_change[13]=100;
position_change[14]=130;
position_change[15]=-100;
p_to_p(20,0);
delay10ms(1);
for(i=0;i<4;i++)
{
position_change[12]=130;
position_change[14]=-130;
p_to_p(15,0);
delay10ms(1);
position_change[12]=-130;
position_change[14]=130;
p_to_p(15,0);
delay10ms(1);
}
position_change[12]=130;
position_change[13]=-100;
position_change[14]=-130;
position_change[15]=100;
p_to_p(20,0);
delay10ms(1);
position_change[6]=110;
position_change[7]=-110;
p_to_p(20,0);

delay1s(1);
}
//#############################################################################
// 函数名称：void ticao()
// 函数说明：体操表演
// 入口参数：无
// 出口参数：无
//#############################################################################
void ticao(void)
{
    
	  initial_position();	
      delay10ms(10);
	  jingli_r();		                          //鞠躬
	  delay500ms(1);
	  tice_yd();					              //体测运动鼓掌  //tc
	  delay500ms(1);
	  switch (part)
	  {
	   
	   case 1:
	   case 3:
	   case 5:
	   case 7:    
	   case 9:    
	   case 11:   cs_xd_left();					//侧身下蹲，头向左扭        
                  delay500ms(1);
	  		      shenzhan();					//伸展
			      delay500ms(1);
	              kuoxiong();				    //扩胸
			      delay500ms(1);
	 		      cs_xd_right();     			//侧身下蹲，头向右扭
                  delay500ms(1);
			   break;
	   case 2:
	   case 4:
	   case 6:
	   case 8:
	   case 10:
	   case 12:
	             cs_xd_right();					//侧身下蹲，头向右扭
	             delay500ms(1);
		  		 shenzhan();
	             delay500ms(1);
		         kuoxiong();
	 			 delay500ms(1);
			     cs_xd_left();					//侧身下蹲，头向左扭        
                 delay500ms(1);
			   break;
	    default: 
                      break;
		}
	py_ss_left();								
	delay500ms(1);
	py_ss_right();
		
    xq_td();			                        //胸前头顶摇摆
	
}
