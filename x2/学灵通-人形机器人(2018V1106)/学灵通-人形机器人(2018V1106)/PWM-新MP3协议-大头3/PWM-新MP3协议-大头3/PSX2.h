
/*---------------------------------------------------------------------*/
/* --- STC MCU International Limited ----------------------------------*/
/* --- STC 1T Series MCU Demo Programme -------------------------------*/
/*---------------------------------------------------------------------*/

#include "REG15W4Kxx.h"

sbit	P_PM25VF040_CE	= P5^4;		//PIN1
sbit	P_PM25VF040_SO	= P1^4;		//PIN2
sbit	P_PM25VF040_SI	= P1^3;		//PIN5
sbit	P_PM25VF040_SCK	= P1^5;		//PIN6

#define	SPI_CE_High()	P_PM25VF040_CE	= 1		/* set CE high 		*/
#define	SPI_CE_Low()	P_PM25VF040_CE	= 0		/* clear CE low 	*/

#define NOP1()  _nop_()
#define NOP(N)  NOP##N()

#define	D_SPI_shift	1		// 0: 不用移位(代码多一点,速度快), 1: 用移位(代码少,速度稍慢)

unsigned char psx_mode = 0x41;  
unsigned char psx_key = 0xFF;
unsigned char psx_key_buff = 0xFF;
unsigned char psx_key_buff_flag = 0x00;

bit anjian_bit;
bit anjian_bit_flag;

/************************************************************************/
void Delay4us_PSX(void)		//@22.1184MHz
{
	unsigned char i, j;

	_nop_();
	i = 1;
	j = 217;
	do
	{
		while (--j);
	} while (--i);
}
void Delay1ms_PSX(void)		//@22.1184MHz
{
	unsigned char i;

	i = 108;
	while (--i);
}
/************************************************************************/
void SPI_init(void)
{
	SPI_CE_High();
	P_PM25VF040_SCK = 0;	/* set clock to low initial state */
	P_PM25VF040_SI = 1;
}

/************************************************************************/
void SPI_WriteByte(unsigned char out)
{
	#if	(D_SPI_shift > 0)
		u8 i;
		i = 8;
		do{
			out <<= 1;
			P_PM25VF040_SI  = CY;
			P_PM25VF040_SCK = 1;//Delay1ms_PSX();
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;	
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;

			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;		
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
//			P_PM25VF040_SCK = 1;
//			P_PM25VF040_SCK = 1;			
			
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;	
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;	
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;	

			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
//			P_PM25VF040_SCK = 0;
//			P_PM25VF040_SCK = 0;
		}while(--i);
	#else
		B = out;
		P_PM25VF040_SI = B7;	P_PM25VF040_SCK = 1;	P_PM25VF040_SCK = 0;	P_PM25VF040_SI = B6;	P_PM25VF040_SCK = 1;	P_PM25VF040_SCK = 0;
		P_PM25VF040_SI = B5;	P_PM25VF040_SCK = 1;	P_PM25VF040_SCK = 0;	P_PM25VF040_SI = B4;	P_PM25VF040_SCK = 1;	P_PM25VF040_SCK = 0;
		P_PM25VF040_SI = B3;	P_PM25VF040_SCK = 1;	P_PM25VF040_SCK = 0;	P_PM25VF040_SI = B2;	P_PM25VF040_SCK = 1;	P_PM25VF040_SCK = 0;
		P_PM25VF040_SI = B1;	P_PM25VF040_SCK = 1;	P_PM25VF040_SCK = 0;	P_PM25VF040_SI = B0;	P_PM25VF040_SCK = 1;	P_PM25VF040_SCK = 0;
	#endif
		P_PM25VF040_SI = 1;
}

/************************************************************************/
unsigned char SPI_ReadByte(void)
{
	#if	(D_SPI_shift > 0)
		u8 i, in;
		i = 8;
		do{
			in <<= 1;
			if (P_PM25VF040_SO)	in++;
			P_PM25VF040_SCK = 1;//Delay1ms_PSX();
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;	
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;	

			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
			P_PM25VF040_SCK = 1;
//			P_PM25VF040_SCK = 1;
//			P_PM25VF040_SCK = 1;
			
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;	
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;	
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;	

			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
			P_PM25VF040_SCK = 0;
//			P_PM25VF040_SCK = 0;
//			P_PM25VF040_SCK = 0;
      //_nop_();
			//_nop_();
		}while(--i);
		return in;

	#else
		B7 = P_PM25VF040_SO;	P_PM25VF040_SCK = 1;	P_PM25VF040_SCK = 0;	NOP(1);	B6 = P_PM25VF040_SO;	P_PM25VF040_SCK = 1;	P_PM25VF040_SCK = 0;  NOP(1);	
		B5 = P_PM25VF040_SO;	P_PM25VF040_SCK = 1;	P_PM25VF040_SCK = 0;	NOP(1);	B4 = P_PM25VF040_SO;	P_PM25VF040_SCK = 1;	P_PM25VF040_SCK = 0;  NOP(1);	
		B3 = P_PM25VF040_SO;	P_PM25VF040_SCK = 1;	P_PM25VF040_SCK = 0;	NOP(1);	B2 = P_PM25VF040_SO;	P_PM25VF040_SCK = 1;	P_PM25VF040_SCK = 0;  NOP(1);	
		B1 = P_PM25VF040_SO;	P_PM25VF040_SCK = 1;	P_PM25VF040_SCK = 0;	NOP(1);	B0 = P_PM25VF040_SO;	P_PM25VF040_SCK = 1;	P_PM25VF040_SCK = 0;  NOP(1);	
		return B;
	#endif
}

//==================================================================
void Clear_PSXBuff(void)
{
	unsigned char i = 0, j = 0;
	unsigned char psx_buff[9] = {0};

	SPI_CE_Low();  
  Delay4us_PSX();/////////+++++++++++++++++  
	while(i < 9)
	{
		if(i == 0)
			j = 0x01;
		else 
		{
			if(i == 1)
				j = 0x42;
			else j = 0xFF;
		}
		SPI_WriteByte(j);                            
		psx_buff[i] = SPI_ReadByte();
		Delay4us_PSX();
		i++;
	}
	SPI_CE_High();   
}
//===================================================================
void Obtain_PSXCode(void)
{
	unsigned char i = 0, j = 0;
	unsigned char psx_buff[9] = {0};
	unsigned int  psx_key_buff = 0;

	SPI_CE_Low();  
  Delay4us_PSX();/////////+++++++++++++++++  
	while(i < 9)
	{
		if(i == 0)
			j = 0x01;
		else 
		{
			if(i == 1)
				j = 0x42;
			else j = 0xFF;
		}
		SPI_WriteByte(j);                            
		psx_buff[i] = SPI_ReadByte();
		Delay4us_PSX();
		i++;
	}
	SPI_CE_High();
	
	if(psx_buff[1] != 0xFF)
	{    
		if(psx_buff[1] != psx_mode)
		{
			psx_mode = psx_buff[1];
			psx_key = 42;
			return;		
		}
	}
	psx_key_buff = psx_buff[3] << 8;
	psx_key_buff = psx_key_buff | psx_buff[4];
	if(psx_key_buff != 0xFFFF)
	{
		switch(psx_key_buff)
		{
			case 0xEFFF: psx_key = 1; break;  
			case 0xDFFF: psx_key = 2; break;  
			case 0xBFFF: psx_key = 3; break;  
			case 0x7FFF: psx_key = 4; break;  

			case 0xFFEF: psx_key = 5; break;  
			case 0xFFDF: psx_key = 6; break;  
			case 0xFFBF: psx_key = 7; break;  
			case 0xFF7F: psx_key = 8; break;  

			case 0xEFEF: psx_key = 9; break;  
			case 0xEFDF: psx_key = 10; break;  
			case 0xEFBF: psx_key = 11; break;  
			case 0xEF7F: psx_key = 12; break;  
			case 0xDFEF: psx_key = 13; break;  
			case 0xDFDF: psx_key = 14; break;  
			case 0xDFBF: psx_key = 15; break;  
			case 0xDF7F: psx_key = 16; break;  
			case 0xBFEF: psx_key = 17; break;  
			case 0xBFDF: psx_key = 18; break;  
			case 0xBFBF: psx_key = 19; break;  
			case 0xBF7F: psx_key = 20; break;  
			case 0x7FEF: psx_key = 21; break;  
			case 0x7FDF: psx_key = 22; break;  
			case 0x7FBF: psx_key = 23; break;  
			case 0x7F7F: psx_key = 24; break;  

			case 0xFFF0: psx_key = 25; break;  
			case 0xFFF1: psx_key = 26; break;  
			case 0xFFF2: psx_key = 27; break;  
			case 0xFFF3: psx_key = 28; break;  
			case 0xFFF4: psx_key = 29; break;  	
			case 0xFFF5: psx_key = 30; break;  
			case 0xFFF6: psx_key = 31; break;  
			case 0xFFF7: psx_key = 32; break;  
			case 0xFFF8: psx_key = 33; break;  	 
			case 0xFFF9: psx_key = 34; break;  
			case 0xFFFA: psx_key = 35; break;  
			case 0xFFFB: psx_key = 36; break;  
			case 0xFFFC: psx_key = 37; break;  	 
			case 0xFFFD: psx_key = 38; break;  
			case 0xFFFE: psx_key = 39; break;  

			case 0xFEFF: psx_key = 40; break;  
			case 0xF7FF: psx_key = 41; break;  
			case 0xF6FF: psx_key = 0;  break;  
			case 0xFDFF: psx_key = 43; break;  
			case 0xFBFF: psx_key = 44; break;  
			case 0xF9FF: psx_key = 45; break;

			default: psx_key = 0xFF;break;
		}
		if(psx_key != 0xFF)
			return;
	}else psx_key = 0xFF;
	if(psx_buff[1] == 0x73)
	{	
		psx_buff[0] = 0;
		if(psx_buff[7] == 0x00)
			psx_buff[0] |= 0x80;     	
		else
		{
			if(psx_buff[7] == 0xFF)
				psx_buff[0] |= 0x40; 			
		}
		if(psx_buff[8] == 0x00)
			psx_buff[0] |= 0x20;     
		else
		{
			if(psx_buff[8] == 0xFF)
				psx_buff[0] |= 0x10; 			
		}
		if(psx_buff[5] == 0x00)
			psx_buff[0] |= 0x08;     
		else
		{
			if(psx_buff[5] == 0xFF)
				psx_buff[0] |= 0x04; 				
		}
		if(psx_buff[6] == 0x00)
			psx_buff[0] |= 0x02;    
		else
		{
			if(psx_buff[6] == 0xFF)
				psx_buff[0] |= 0x01; 			
		}
		switch(psx_buff[0])
		{
			case 0x20: psx_key = 51; break;     
			case 0x40: psx_key = 52; break;  
			case 0x10: psx_key = 53; break;  
			case 0x80: psx_key = 54; break;  

			case 0x02: psx_key = 55; break;  	     
			case 0x04: psx_key = 56; break;  
			case 0x01: psx_key = 57; break;  
			case 0x08: psx_key = 58; break;  

		/*	case 0x22: psx_key = 59; break;  	     
			case 0x24: psx_key = 60; break;  
			case 0x21: psx_key = 61; break;  
			case 0x28: psx_key = 62; break;  
			case 0x42: psx_key = 63; break;  	 			       
			case 0x44: psx_key = 64; break;  
			case 0x41: psx_key = 65; break; 
			case 0x48: psx_key = 66; break;  
			case 0x12: psx_key = 67; break;   			        
			case 0x14: psx_key = 68; break;  
			case 0x11: psx_key = 69; break;  
			case 0x18: psx_key = 70; break;  
			case 0x82: psx_key = 71; break;                    
			case 0x84: psx_key = 72; break;  
			case 0x81: psx_key = 73; break;  
			case 0x88: psx_key = 74; break;  */
			default: psx_key = 0xFF;break;			
		}				  
	}		
}

//========================================================================
void PSXKey_Filter(void)
{
	if((psx_key != 0xFF) && (psx_key != 42))
	{
		if(psx_mode == 0x41)
		{
			if((psx_key == 1) || (psx_key == 3))
				anjian_bit_flag = 1;
		}
		else
		{
			if((psx_key == 51) || (psx_key == 53))
				anjian_bit_flag = 1;			
		}
		if(psx_key_buff != psx_key)
		{
			psx_key_buff = psx_key;
			psx_key_buff_flag = 0;
			psx_key = 0xFF;
		} 
		else 
		{
			psx_key_buff_flag++;
			if(psx_key_buff_flag < 3)
				psx_key = 0xFF;
		}			
	}
	else
	{
		if(anjian_bit_flag == 1)
		{
			anjian_bit = 1;
			anjian_bit_flag = 0;
		}
	}
}

/************************************************
检测Flash的忙状态
入口参数: 无
出口参数:
    0 : Flash处于空闲状态
    1 : Flash处于忙状态
************************************************/
/*u8	CheckFlashBusy(void)
{
	u8	dat;

	SPI_CE_Low();
	SPI_WriteByte(SFC_RDSR);		//发送读取状态命令
	dat = SPI_ReadByte();			//读取状态
	SPI_CE_High();

	return (dat);					//状态值的Bit0即为忙标志
}
*/


