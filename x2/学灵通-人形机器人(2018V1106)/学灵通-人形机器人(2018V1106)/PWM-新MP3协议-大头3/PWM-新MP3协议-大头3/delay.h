#define uchar    unsigned char
#define uint     unsigned short int
#define uint32   unsigned long int
#define sint8    signed char
#define sint16   signed short int
#define sint32   signed long int
#define uint64   unsigned long long int
#define sint64   signed long long int

extern void delay8us(unsigned char num);            //把delay_8us()声明为外部函数
extern void delay10us(unsigned char num);           //把delay_10us()声明为外部函数
extern void delay100us(unsigned char num);          //把delay_100us()声明为外部函数
//extern void delay490us(unsigned char num);          //把delay_490us()声明为外部函数
extern void delay500us(unsigned char num);          //把delay_500us()声明为外部函数
extern void delay1ms(unsigned char num);            //把delay_1ms()声明为外部函数
extern void delay10ms(unsigned char num);           //把delay_10ms()声明为外部函数
extern void delay500ms(unsigned char num);          //把delay_500ms()声明为外部函数
extern void delay1s(unsigned char num);             //把delay_1000ms()声明为外部函数	   
