class ScalingStrategy:

    @classmethod
    def _convert_to_amr_param(cls, box: list) -> str:
        value = " ".join(str(x) for x in box)
        return (f'({value})', f'amr.n_cell={value}')
    
    @classmethod
    def weak_3d_scaling(cls, init_box:list, init_cores: int, max_cores: int):
        dim = len(init_box) #todo: raise error when it's zero 
        core_dict = {}
        cores = init_cores
        box = init_box[:]
        while cores <= max_cores:
            core_dict[cores] = cls._convert_to_amr_param(box)
            box = [x * 2 for x in box]            
            cores *= 2**dim
        return core_dict