# Code structure

- train.py Main program
<details>
Example run:

```
python3.6  train.py --prefix new_ --name test --dataset phutho --epoch 30 --early_stop 5 --batch_size 32 --worker 16 --loss adaptive --gpu 0 --wandb true --model resnet50
```

</details>

- labels_tree.py Hierarchical tree structure
- losses.py custom loss functions
