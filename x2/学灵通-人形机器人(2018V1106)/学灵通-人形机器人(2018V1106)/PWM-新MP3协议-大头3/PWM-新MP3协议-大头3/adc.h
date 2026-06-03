#ifndef H_ADC_H_
#define H_ADC_H_

extern void initial_adc(void);
extern void start_adc(void);
extern void get_balance_value(void);
extern void get_present_value(void);
extern void adc_adjust(void);
extern unsigned char flag_balance;
extern unsigned char flag_adjust;
extern unsigned char flag_jump;

extern unsigned int balance_value[3];

#endif
