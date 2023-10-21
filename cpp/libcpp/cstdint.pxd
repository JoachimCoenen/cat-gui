cdef extern from "<cstdint>" nogil:
	ctypedef signed char        int8_t
	ctypedef short              int16_t
	ctypedef int                int32_t
	ctypedef long long          int64_t
	ctypedef unsigned char      uint8_t
	ctypedef unsigned short     uint16_t
	ctypedef unsigned int       uint32_t
	ctypedef unsigned long long uint64_t

	ctypedef signed char        int_least8_t
	ctypedef short              int_least16_t
	ctypedef int                int_least32_t
	ctypedef long long          int_least64_t
	ctypedef unsigned char      uint_least8_t
	ctypedef unsigned short     uint_least16_t
	ctypedef unsigned int       uint_least32_t
	ctypedef unsigned long long uint_least64_t

	ctypedef signed char        int_fast8_t
	ctypedef int                int_fast16_t
	ctypedef int                int_fast32_t
	ctypedef long long          int_fast64_t
	ctypedef unsigned char      uint_fast8_t
	ctypedef unsigned int       uint_fast16_t
	ctypedef unsigned int       uint_fast32_t
	ctypedef unsigned long long uint_fast64_t

	ctypedef long long          intmax_t
	ctypedef unsigned long long uintmax_t


cdef extern from "<cstdint>" nogil:
	int8_t         INT8_MIN           # = (-127i8 - 1)
	int16_t        INT16_MIN          # = (-32767i16 - 1)
	int32_t        INT32_MIN          # = (-2147483647i32 - 1)
	int64_t        INT64_MIN          # = (-9223372036854775807i64 - 1)
	int8_t         INT8_MAX           # = 127i8
	int16_t        INT16_MAX          # = 32767i16
	int32_t        INT32_MAX          # = 2147483647i32
	int64_t        INT64_MAX          # = 9223372036854775807i64
	uint8_t        UINT8_MAX          # = 0xffui8
	uint16_t       UINT16_MAX         # = 0xffffui16
	uint32_t       UINT32_MAX         # = 0xffffffffui32
	uint64_t       UINT64_MAX         # = 0xffffffffffffffffui64

	int_least8_t   INT_LEAST8_MIN     # = INT8_MIN
	int_least16_t  INT_LEAST16_MIN    # = INT16_MIN
	int_least32_t  INT_LEAST32_MIN    # = INT32_MIN
	int_least64_t  INT_LEAST64_MIN    # = INT64_MIN
	int_least8_t   INT_LEAST8_MAX     # = INT8_MAX
	int_least16_t  INT_LEAST16_MAX    # = INT16_MAX
	int_least32_t  INT_LEAST32_MAX    # = INT32_MAX
	int_least64_t  INT_LEAST64_MAX    # = INT64_MAX
	uint_least8_t  UINT_LEAST8_MAX    # = UINT8_MAX
	uint_least16_t UINT_LEAST16_MAX   # = UINT16_MAX
	uint_least32_t UINT_LEAST32_MAX   # = UINT32_MAX
	uint_least64_t UINT_LEAST64_MAX   # = UINT64_MAX

	int_fast8_t    INT_FAST8_MIN      # = INT8_MIN
	int_fast16_t   INT_FAST16_MIN     # = INT32_MIN
	int_fast32_t   INT_FAST32_MIN     # = INT32_MIN
	int_fast64_t   INT_FAST64_MIN     # = INT64_MIN
	int_fast8_t    INT_FAST8_MAX      # = INT8_MAX
	int_fast16_t   INT_FAST16_MAX     # = INT32_MAX
	int_fast32_t   INT_FAST32_MAX     # = INT32_MAX
	int_fast64_t   INT_FAST64_MAX     # = INT64_MAX
	uint_fast8_t   UINT_FAST8_MAX     # = UINT8_MAX
	uint_fast16_t  UINT_FAST16_MAX    # = UINT32_MAX
	uint_fast32_t  UINT_FAST32_MAX    # = UINT32_MAX
	uint_fast64_t  UINT_FAST64_MAX    # = UINT64_MAX

	# intptr_t   INTPTR_MIN         # = INT64_MIN  or INT32_MIN
	# intptr_t   INTPTR_MAX         # = INT64_MAX  or INT32_MAX
	# uintptr_t  UINTPTR_MAX        # = UINT64_MAX or UINT32_MAX

	intmax_t       INTMAX_MIN         # = INT64_MIN
	intmax_t       INTMAX_MAX         # = INT64_MAX
	uintmax_t      UINTMAX_MAX        # = UINT64_MAX
