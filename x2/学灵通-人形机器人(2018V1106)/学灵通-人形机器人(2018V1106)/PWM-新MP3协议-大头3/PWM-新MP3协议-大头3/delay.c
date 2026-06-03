//ÑÓÊ±ÎÄ¼ş
#include <intrins.h>
#define uchar unsigned char
#define uint  unsigned int

void delay8us(uchar num)
{
unsigned char i,j;
for(j=0;j<num;j++)
//for (k=0;k<1;k++)
//for (m=0;m<1;m++)
for (i=0;i<1;i++); 


/*	unsigned char i,j;
  for(j=0;j<num;j++)
	{
		//_nop_();
		//_nop_();
		i = 2;
		while (--i);
	}		  */
}	

void delay10us(uchar num)
{uchar i,j;
for(j=0;j<num;j++)
for (i=0;i<11;i++)
;
}
 
void delay100us(uchar num)
{uchar i,j;
for(j=0;j<num;j++)
for (i=0;i<1;i++)
delay10us(11);
}

/*void delay490us(uchar num)
{	unsigned char i,j,k;
  for(k=0;k<num;k++)
	{
		//_nop_();
		//_nop_();
		//_nop_();
		i = 5;
		j = 1;
		do
		{
			while (--j);
		} while (--i);
	}
} 	 */
void delay500us(uchar num)
{
/*uchar i,j;
for(j=0;j<num;j++)
for (i=0;i<1;i++)
delay10us(55);*/
	unsigned char i,j,k;
  for(k=0;k<num;k++)
	{
		//_nop_();
		//_nop_();
		//_nop_();
		i = 6;
		j = 1;
		do
		{
			while (--j);
		} while (--i);
	}
}


void delay1ms(uchar num)
{uchar i,j;
for(j=0;j<num;j++)
for (i=0;i<1;i++)
delay10us(122);
}

void delay10ms(uchar num)
{uchar i,j;
for(j=0;j<num;j++)
for (i=0;i<1;i++)
delay1ms(10);
}

void delay500ms(uchar num)
{uchar i,j;
for(j=0;j<num;j++)
for (i=0;i<50;i++)
delay1ms(10);
}

void delay1s(uchar num)
{uchar i,j;
for(j=0;j<num;j++)
for (i=0;i<1;i++)
delay10ms(100);
}


